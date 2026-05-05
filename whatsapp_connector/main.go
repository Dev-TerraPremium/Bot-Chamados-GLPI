package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"

	_ "modernc.org/sqlite"

	"github.com/mdp/qrterminal/v3"
	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types/events"
	"go.mau.fi/whatsmeow/proto/waE2E"
	waLog "go.mau.fi/whatsmeow/util/log"
	"google.golang.org/protobuf/proto"
)

type BotRequest struct {
	SessionID         string `json:"session_id"`
	Message           string `json:"message"`
	ChannelIdentifier string `json:"channel_identifier"`
}

type BotResponse struct {
	SessionID  string `json:"session_id"`
	BotMessage string `json:"bot_message"`
	State      string `json:"state"`
}

var client *whatsmeow.Client

func eventHandler(evt interface{}) {
	switch v := evt.(type) {
	case *events.Message:
		if v.Info.IsFromMe {
			return
		}
		if v.Info.IsGroup {
			return
		}

		var text string
		if v.Message.GetConversation() != "" {
			text = v.Message.GetConversation()
		} else if v.Message.GetExtendedTextMessage() != nil {
			text = v.Message.GetExtendedTextMessage().GetText()
		}

		if text == "" {
			return
		}

		// O número do WhatsApp vem algo como 5511999999999
		senderPhone := v.Info.Sender.User
		fmt.Printf("Nova mensagem de %s: %s\n", senderPhone, text)

		// Dispara para a API FastAPI em background
		go func() {
			reqBody := BotRequest{
				SessionID:         senderPhone,
				Message:           text,
				ChannelIdentifier: senderPhone, // O canal de identificação é o número
			}
			jsonData, err := json.Marshal(reqBody)
			if err != nil {
				fmt.Println("Erro marshal JSON:", err)
				return
			}

			// Endpoint do FastAPI local (mude se necessário)
			resp, err := http.Post("http://127.0.0.1:8000/api/conversation/message", "application/json", bytes.NewBuffer(jsonData))
			if err != nil {
				fmt.Println("Erro requisicao FastAPI:", err)
				return
			}
			defer resp.Body.Close()

			body, err := io.ReadAll(resp.Body)
			if err != nil {
				fmt.Println("Erro lendo reposta:", err)
				return
			}

			var botResp BotResponse
			err = json.Unmarshal(body, &botResp)
			if err != nil {
				fmt.Println("Erro parse JSON resposta:", err)
				return
			}

			botMsg := strings.TrimSpace(botResp.BotMessage)
			if botMsg != "" {
				_, err = client.SendMessage(context.Background(), v.Info.Sender, &waE2E.Message{
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
	// 1. Inicia o banco local SQLite (modernc sem CGO para facilitar no Windows)
	dbLog := waLog.Stdout("Database", "ERROR", true)
	container, err := sqlstore.New(context.Background(), "sqlite", "file:store.db?_pragma=foreign_keys(1)", dbLog)
	if err != nil {
		panic(err)
	}

	// 2. Cria o device (gerencia as chaves de sessão do WhatsApp Web)
	deviceStore, err := container.GetFirstDevice(context.Background())
	if err != nil {
		panic(err)
	}

	// 3. Inicializa o cliente WhatsMeow
	clientLog := waLog.Stdout("Client", "INFO", true)
	client = whatsmeow.NewClient(deviceStore, clientLog)
	client.AddEventHandler(eventHandler)

	// 4. Conecta. Se for o primeiro acesso, gera o QR Code no terminal.
	if client.Store.ID == nil {
		qrChan, _ := client.GetQRChannel(context.Background())
		err = client.Connect()
		if err != nil {
			panic(err)
		}
		for evt := range qrChan {
			if evt.Event == "code" {
				qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
				fmt.Println("\n\n🤖 QR Code gerado! Abra seu WhatsApp no celular e escaneie o código acima.")
			} else {
				fmt.Println("Evento do QR:", evt.Event)
			}
		}
	} else {
		// Já autenticado, só conecta
		err = client.Connect()
		if err != nil {
			panic(err)
		}
		fmt.Println("✅ Bot do WhatsApp conectado com sucesso!")
	}

	// 5. Trava o processo rodando até receber SIGINT (Ctrl+C)
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c

	client.Disconnect()
}
