# Visao de arquitetura

O projeto separa canal, conversa, dominio, triagem, seguranca, persistencia simulada e fronteira GLPI.

```mermaid
flowchart TD
    Web[Web Simulator] --> Adapter[Adaptador de canal]
    Telegram[Telegram futuro] --> Adapter
    WhatsApp[WhatsApp futuro] --> Adapter
    Teams[Microsoft Teams futuro] --> Adapter
    Adapter --> Engine[Motor unico de conversa]
    Engine --> Security[Protecoes de entrada]
    Engine --> Domain[Servicos de dominio de chamado]
    Domain --> GLPI[Camada reservada GLPI]
    GLPI --> Mock[Mock em memoria]
    GLPI -. futuro .-> RealGLPI[GLPI REST real]
```

Os canais nao possuem regra de negocio. A troca de canal deve preservar o mesmo fluxo e os mesmos servicos.

