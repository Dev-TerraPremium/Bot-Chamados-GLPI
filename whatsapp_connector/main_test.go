package main

import "testing"

func TestShouldSendSlowProcessingNotice(t *testing.T) {
	testCases := []struct {
		name      string
		lastState string
		text      string
		media     int
		want      bool
	}{
		{
			name:      "description collection triggers notice",
			lastState: "description_collection",
			text:      "Minha nota nao autoriza",
			want:      true,
		},
		{
			name:      "clarification triggers notice",
			lastState: "description_clarification",
			text:      "Erro 302 na tela fiscal",
			want:      true,
		},
		{
			name:      "evidence collection only warns on done command",
			lastState: "evidence_collection",
			text:      "pronto",
			want:      true,
		},
		{
			name:      "evidence text alone does not warn",
			lastState: "evidence_collection",
			text:      "segue um detalhe",
			want:      false,
		},
		{
			name:      "menu state does not warn",
			lastState: "main_menu",
			text:      "1",
			want:      false,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			got := shouldSendSlowProcessingNotice(tc.lastState, tc.text, tc.media)
			if got != tc.want {
				t.Fatalf("shouldSendSlowProcessingNotice(%q, %q, %d) = %v, want %v", tc.lastState, tc.text, tc.media, got, tc.want)
			}
		})
	}
}

func TestIsEvidenceDoneCommand(t *testing.T) {
	for _, text := range []string{"pronto", "PRONTO", " ok ", "finalizar", "concluir"} {
		if !isEvidenceDoneCommand(text) {
			t.Fatalf("expected %q to be treated as done command", text)
		}
	}
	if isEvidenceDoneCommand("segue mais um print") {
		t.Fatal("unexpected done command detection for regular evidence text")
	}
}
