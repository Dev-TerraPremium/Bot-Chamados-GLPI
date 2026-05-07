package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"sync"
	"syscall"
	"time"

	_ "modernc.org/sqlite"

	"github.com/mdp/qrterminal/v3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
)

type AttachmentPayload struct {
	MimeType   string `json:"mime_type"`
	FileName   string `json:"file_name"`
	DataBase64 string `json:"data_base64"`
}

type BotRequest struct {
	SessionID         string              `json:"session_id"`
	Channel           string              `json:"channel"`
	Message           string              `json:"message"`
	ChannelIdentifier string              `json:"channel_identifier"`
	Media             []AttachmentPayload `json:"media,omitempty"`
}

type BotResponse struct {
	SessionID  string `json:"session_id"`
	BotMessage string `json:"bot_message"`
	State      string `json:"state"`
}

var client *whatsmeow.Client
var connectorStartedAt = time.Now()
var digitsOnly = regexp.MustCompile(`\D+`)
var inflightMu sync.Mutex
var inflightBySender = map[string]inflightEntry{}

type inflightEntry struct {
	startedAt    time.Time
	lastNoticeAt time.Time
}

const inflightTTL = 5 * time.Minute
const busyNoticeInterval = 15 * time.Second
const busyMessage = "Ainda estou processando sua resposta anterior. Aguarde eu enviar a próxima mensagem antes de digitar outra opção."

func normalizePhone(value string) string {
	digits := digitsOnly.ReplaceAllString(value, "")
	if strings.HasPrefix(digits, "55") && len(digits) > 11 {
		return strings.TrimPrefix(digits, "55")
	}
	return digits
}

func phoneVariants(value string) []string {
	normalized := normalizePhone(value)
	if normalized == "" {
		return nil
	}

	variants := []string{normalized}
	if len(normalized) == 11 && normalized[2] == '9' {
		variants = append(variants, normalized[:2]+normalized[3:])
	}
	if len(normalized) == 10 {
		variants = append(variants, normalized[:2]+"9"+normalized[2:])
	}
	return variants
}

func allowedNumbers() map[string]bool {
	allowed := make(map[string]bool)
	for _, n := range strings.Split(os.Getenv("ALLOWED_NUMBERS"), ",") {
		for _, variant := range phoneVariants(strings.TrimSpace(n)) {
			allowed[variant] = true
		}
	}
	return allowed
}

func isExplicitlyAllowed(senderPhone string) bool {
	if strings.EqualFold(os.Getenv("ALLOW_ALL_NUMBERS"), "true") {
		return true
	}
	allowed := allowedNumbers()
	if len(allowed) == 0 {
		return false
	}
	for _, variant := range phoneVariants(senderPhone) {
		if allowed[variant] {
			return true
		}
	}
	return false
}

func shouldLogIgnoredMessages() bool {
	return strings.EqualFold(os.Getenv("LOG_IGNORED_MESSAGES"), "true")
}

func logIgnored(reason string, v *events.Message, details string) {
	if !shouldLogIgnoredMessages() {
		return
	}
	if details != "" {
		details = " " + details
	}
	fmt.Printf("Mensagem ignorada (%s): chat=%s sender=%s ts=%s%s\n", reason, v.Info.Chat.String(), v.Info.Sender.String(), v.Info.Timestamp.Format(time.RFC3339), details)
}

func isDirectUserServer(server string) bool {
	return server == types.DefaultUserServer || server == types.HiddenUserServer
}

func shouldIgnoreMessage(v *events.Message) (bool, string) {
	if v.Info.IsFromMe {
		return true, "from_me"
	}
	if v.Info.Timestamp.Before(connectorStartedAt.Add(-30 * time.Second)) {
		return true, "history_sync"
	}
	if v.Info.IsGroup || v.Info.Chat.Server == "g.us" || v.Info.Chat.IsBroadcastList() || v.Info.IsIncomingBroadcast() {
		return true, "group_or_broadcast"
	}
	if v.Info.Sender.Server == "newsletter" || v.Info.Sender.Server == "broadcast" || v.Info.Sender.Server == "g.us" {
		return true, "sender_not_direct_user"
	}
	if !isDirectUserServer(v.Info.Chat.Server) {
		return true, "chat_not_direct_user"
	}
	if !isDirectUserServer(v.Info.Sender.Server) && !isDirectUserServer(v.Info.SenderAlt.Server) {
		return true, "sender_not_direct_user"
	}
	return false, ""
}

func phoneFromJID(ctx context.Context, jid types.JID) string {
	jid = jid.ToNonAD()
	if jid.Server == types.DefaultUserServer {
		return jid.User
	}
	if jid.Server != types.HiddenUserServer || client == nil || client.Store == nil {
		return ""
	}
	phoneJID, err := client.Store.GetAltJID(ctx, jid)
	if err != nil || phoneJID.IsEmpty() || phoneJID.Server != types.DefaultUserServer {
		return ""
	}
	return phoneJID.User
}

func resolveSenderPhone(ctx context.Context, v *events.Message) string {
	candidates := []types.JID{
		v.Info.SenderAlt,
		v.Info.Sender,
		v.Info.Chat,
	}
	for _, candidate := range candidates {
		if phone := phoneFromJID(ctx, candidate); phone != "" {
			return phone
		}
	}
	return ""
}

func extractText(message *waE2E.Message) string {
	if message.GetConversation() != "" {
		return message.GetConversation()
	}
	if message.GetExtendedTextMessage() != nil {
		return message.GetExtendedTextMessage().GetText()
	}
	if message.GetImageMessage() != nil {
		return message.GetImageMessage().GetCaption()
	}
	if message.GetVideoMessage() != nil {
		return message.GetVideoMessage().GetCaption()
	}
	if message.GetDocumentMessage() != nil {
		return message.GetDocumentMessage().GetCaption()
	}
	return ""
}

func hasSupportedMedia(message *waE2E.Message) bool {
	return message.GetImageMessage() != nil ||
		message.GetDocumentMessage() != nil ||
		message.GetVideoMessage() != nil ||
		message.GetAudioMessage() != nil ||
		message.GetStickerMessage() != nil
}

func extensionForMime(mimeType string) string {
	switch {
	case strings.Contains(mimeType, "jpeg"):
		return ".jpg"
	case strings.Contains(mimeType, "png"):
		return ".png"
	case strings.Contains(mimeType, "webp"):
		return ".webp"
	case strings.Contains(mimeType, "mp4"):
		return ".mp4"
	case strings.Contains(mimeType, "ogg"):
		return ".ogg"
	case strings.Contains(mimeType, "mpeg"):
		return ".mp3"
	case strings.Contains(mimeType, "pdf"):
		return ".pdf"
	default:
		return ""
	}
}

func appendDownloadedMedia(ctx context.Context, payloads []AttachmentPayload, messageID string, label string, fileName string, mimeType string, downloader func(context.Context) ([]byte, error)) []AttachmentPayload {
	data, err := downloader(ctx)
	if err != nil {
		fmt.Printf("Erro ao baixar anexo %s: %v\n", label, err)
		return payloads
	}
	if fileName == "" {
		fileName = fmt.Sprintf("%s-%s%s", label, messageID, extensionForMime(mimeType))
	}
	if mimeType == "" {
		mimeType = "application/octet-stream"
	}
	return append(payloads, AttachmentPayload{
		MimeType:   mimeType,
		FileName:   fileName,
		DataBase64: base64.StdEncoding.EncodeToString(data),
	})
}

func collectMediaPayloads(ctx context.Context, message *waE2E.Message, messageID string) []AttachmentPayload {
	var payloads []AttachmentPayload
	if img := message.GetImageMessage(); img != nil {
		payloads = appendDownloadedMedia(ctx, payloads, messageID, "imagem", "", img.GetMimetype(), func(ctx context.Context) ([]byte, error) {
			return client.Download(ctx, img)
		})
	}
	if doc := message.GetDocumentMessage(); doc != nil {
		fileName := doc.GetFileName()
		payloads = appendDownloadedMedia(ctx, payloads, messageID, "documento", fileName, doc.GetMimetype(), func(ctx context.Context) ([]byte, error) {
			return client.Download(ctx, doc)
		})
	}
	if video := message.GetVideoMessage(); video != nil {
		payloads = appendDownloadedMedia(ctx, payloads, messageID, "video", "", video.GetMimetype(), func(ctx context.Context) ([]byte, error) {
			return client.Download(ctx, video)
		})
	}
	if audio := message.GetAudioMessage(); audio != nil {
		payloads = appendDownloadedMedia(ctx, payloads, messageID, "audio", "", audio.GetMimetype(), func(ctx context.Context) ([]byte, error) {
			return client.Download(ctx, audio)
		})
	}
	if sticker := message.GetStickerMessage(); sticker != nil {
		payloads = appendDownloadedMedia(ctx, payloads, messageID, "sticker", "", sticker.GetMimetype(), func(ctx context.Context) ([]byte, error) {
			return client.Download(ctx, sticker)
		})
	}
	return payloads
}

func tryStartProcessing(senderPhone string) (bool, bool) {
	now := time.Now()
	inflightMu.Lock()
	defer inflightMu.Unlock()

	for sender, entry := range inflightBySender {
		if now.Sub(entry.startedAt) > inflightTTL {
			delete(inflightBySender, sender)
		}
	}

	entry, exists := inflightBySender[senderPhone]
	if exists {
		shouldNotify := entry.lastNoticeAt.IsZero() || now.Sub(entry.lastNoticeAt) >= busyNoticeInterval
		if shouldNotify {
			entry.lastNoticeAt = now
			inflightBySender[senderPhone] = entry
		}
		return false, shouldNotify
	}

	inflightBySender[senderPhone] = inflightEntry{startedAt: now}
	return true, false
}

func finishProcessing(senderPhone string) {
	inflightMu.Lock()
	defer inflightMu.Unlock()
	delete(inflightBySender, senderPhone)
}

func sendPlainText(ctx context.Context, target types.JID, text string) {
	if strings.TrimSpace(text) == "" {
		return
	}
	_, err := client.SendMessage(ctx, target, &waE2E.Message{
		Conversation: proto.String(text),
	})
	if err != nil {
		fmt.Println("Erro ao enviar mensagem no WhatsApp:", err)
	}
}

func eventHandler(evt interface{}) {
	switch v := evt.(type) {
	case *events.Message:
		if ignore, reason := shouldIgnoreMessage(v); ignore {
			logIgnored(reason, v, "")
			return
		}

		text := extractText(v.Message)
		if text == "" && !hasSupportedMedia(v.Message) {
			return
		}

		senderPhone := resolveSenderPhone(context.Background(), v)
		if senderPhone == "" {
			logIgnored("lid_unresolved", v, "")
			return
		}
		if !isExplicitlyAllowed(senderPhone) {
			logIgnored("not_allowed", v, fmt.Sprintf("phone=%s", senderPhone))
			return
		}

		sendTarget := v.Info.Chat
		if sendTarget.IsEmpty() {
			sendTarget = v.Info.Sender
		}
		if ok, shouldNotify := tryStartProcessing(senderPhone); !ok {
			logIgnored("processing_in_progress", v, fmt.Sprintf("phone=%s", senderPhone))
			if shouldNotify {
				sendPlainText(context.Background(), sendTarget, busyMessage)
			}
			return
		}

		mediaPayload := collectMediaPayloads(context.Background(), v.Message, v.Info.ID)

		fmt.Printf("Nova mensagem de %s: %s\n", senderPhone, text)

		go func() {
			defer finishProcessing(senderPhone)
			reqBody := BotRequest{
				SessionID:         senderPhone,
				Channel:           "whatsapp",
				Message:           text,
				ChannelIdentifier: senderPhone,
				Media:             mediaPayload,
			}
			jsonData, err := json.Marshal(reqBody)
			if err != nil {
				fmt.Println("Erro marshal JSON:", err)
				return
			}

			apiURL := os.Getenv("BOT_API_URL")
			if apiURL == "" {
				apiURL = "http://127.0.0.1:8000/api/conversation/message"
			}
			resp, err := http.Post(apiURL, "application/json", bytes.NewBuffer(jsonData))
			if err != nil {
				fmt.Println("Erro requisicao FastAPI:", err)
				return
			}
			defer resp.Body.Close()

			body, err := io.ReadAll(resp.Body)
			if err != nil {
				fmt.Println("Erro lendo resposta:", err)
				return
			}
			if resp.StatusCode < 200 || resp.StatusCode >= 300 {
				fmt.Printf("Erro FastAPI status=%d body=%s\n", resp.StatusCode, strings.TrimSpace(string(body)))
				return
			}

			var botResp BotResponse
			err = json.Unmarshal(body, &botResp)
			if err != nil {
				fmt.Printf("Erro parse JSON resposta: %v body=%s\n", err, strings.TrimSpace(string(body)))
				return
			}

			botMsg := strings.TrimSpace(botResp.BotMessage)
			if botMsg != "" {
				sendPlainText(context.Background(), sendTarget, botMsg)
			}
		}()
	}
}

func main() {
	if os.Getenv("ALLOWED_NUMBERS") == "" && !strings.EqualFold(os.Getenv("ALLOW_ALL_NUMBERS"), "true") {
		fmt.Println("ERRO: ALLOWED_NUMBERS vazio. Por seguranca, o conector nao inicia em modo aberto.")
		fmt.Println("Use start_all.ps1 ou defina ALLOW_ALL_NUMBERS=true apenas para teste consciente.")
		os.Exit(1)
	}

	dbLog := waLog.Stdout("Database", "ERROR", true)
	storePath := os.Getenv("WHATSAPP_STORE_PATH")
	if storePath == "" {
		storePath = "store.db"
	}
	connStr := fmt.Sprintf("file:%s?_pragma=foreign_keys(1)&_pragma=journal_mode(WAL)&_pragma=busy_timeout(10000)", storePath)
	container, err := sqlstore.New(context.Background(), "sqlite", connStr, dbLog)
	if err != nil {
		panic(err)
	}

	deviceStore, err := container.GetFirstDevice(context.Background())
	if err != nil {
		panic(err)
	}

	clientLog := waLog.Stdout("Client", "INFO", true)
	client = whatsmeow.NewClient(deviceStore, clientLog)
	client.AddEventHandler(eventHandler)

	if client.Store.ID == nil {
		qrChan, _ := client.GetQRChannel(context.Background())
		err = client.Connect()
		if err != nil {
			panic(err)
		}
		for evt := range qrChan {
			if evt.Event == "code" {
				qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
				fmt.Println("\n\nQR Code gerado. Abra seu WhatsApp no celular e escaneie o codigo acima.")
			} else {
				fmt.Println("Evento do QR:", evt.Event)
			}
		}
	} else {
		err = client.Connect()
		if err != nil {
			panic(err)
		}
		fmt.Println("Bot do WhatsApp conectado com sucesso.")
	}

	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c

	client.Disconnect()
}
