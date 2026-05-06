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
	Base64Data string `json:"base64_data"`
}

type BotRequest struct {
	SessionID         string              `json:"session_id"`
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
	return ""
}

func eventHandler(evt interface{}) {
	switch v := evt.(type) {
	case *events.Message:
		if ignore, reason := shouldIgnoreMessage(v); ignore {
			logIgnored(reason, v, "")
			return
		}

		text := extractText(v.Message)
		if text == "" && v.Message.GetImageMessage() == nil && v.Message.GetDocumentMessage() == nil {
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

		var mediaPayload []AttachmentPayload
		if img := v.Message.GetImageMessage(); img != nil {
			data, err := client.Download(context.Background(), img)
			if err == nil {
				mediaPayload = append(mediaPayload, AttachmentPayload{
					MimeType:   img.GetMimetype(),
					FileName:   "imagem.jpg",
					Base64Data: base64.StdEncoding.EncodeToString(data),
				})
			}
		} else if doc := v.Message.GetDocumentMessage(); doc != nil {
			data, err := client.Download(context.Background(), doc)
			if err == nil {
				fileName := doc.GetFileName()
				if fileName == "" {
					fileName = "documento"
				}
				mediaPayload = append(mediaPayload, AttachmentPayload{
					MimeType:   doc.GetMimetype(),
					FileName:   fileName,
					Base64Data: base64.StdEncoding.EncodeToString(data),
				})
			}
		}

		fmt.Printf("Nova mensagem de %s: %s\n", senderPhone, text)

		go func() {
			reqBody := BotRequest{
				SessionID:         senderPhone,
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
				sendTarget := v.Info.Chat
				if sendTarget.IsEmpty() {
					sendTarget = v.Info.Sender
				}
				_, err = client.SendMessage(context.Background(), sendTarget, &waE2E.Message{
					Conversation: proto.String(botMsg),
				})
				if err != nil {
					fmt.Println("Erro ao enviar mensagem no WhatsApp:", err)
				}
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
	connStr := "file:store.db?_pragma=foreign_keys(1)&_pragma=journal_mode(WAL)&_pragma=busy_timeout(10000)"
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
