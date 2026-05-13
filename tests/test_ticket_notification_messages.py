from app.ticket_notifications.event_reader import GLPITicketEventReader
from app.ticket_notifications.message_renderer import TicketNotificationMessageRenderer
from app.ticket_notifications.models import TicketEvent, WatchedTicket


class FakeLinkedGLPIClient:
    def get_item(self, itemtype: str, item_id: int):
        if itemtype == "Ticket":
            return {"id": item_id, "status": 2, "name": "Chamado teste"}
        if itemtype == "User":
            return {"id": item_id, "firstname": "Ana", "realname": "Silva", "name": "asilva"}
        if itemtype == "Group":
            return {"id": item_id, "name": "Suporte N2"}
        return {"id": item_id}

    def get_ticket_related_items(self, ticket_id: int, itemtype: str):
        if itemtype == "Ticket_User":
            return {
                "items": [
                    {
                        "id": 20,
                        "users_id": 8,
                        "type": 3,
                        "use_notification": 1,
                        "date_creation": "2026-05-11 15:10:00",
                    }
                ]
            }
        if itemtype == "Group_Ticket":
            return {
                "items": [
                    {
                        "id": 21,
                        "groups_id": 5,
                        "type": 2,
                        "date_creation": "2026-05-11 15:11:00",
                    }
                ]
            }
        return {"items": []}


def _watched_ticket() -> WatchedTicket:
    return WatchedTicket(
        ticket_id=9274,
        requester_phone="556699990980",
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        category_name="Infraestrutura",
        title="Mouse e teclado",
        location="Rondonópolis",
        created_at="2026-05-11 15:00:00",
    )


def test_renderer_translates_linked_person_type_and_notification_flag():
    renderer = TicketNotificationMessageRenderer(
        ticket_url_template="https://glpi.local/front/ticket.form.php?id={ticket_id}"
    )
    event = TicketEvent(
        ticket_id=9274,
        event_type="ticket_user_changed",
        source_itemtype="Ticket_User",
        source_id="20",
        occurred_at="2026-05-11 15:10:00",
        is_private=False,
        actor="266",
        old_value="",
        new_value="8",
        raw_payload={
            "users_id": 8,
            "linked_user_name": "Maria Oliveira",
            "type": 3,
            "use_notification": 1,
        },
    )

    message = renderer.render_user_message(_watched_ticket(), event)

    assert "Maria Oliveira" in message
    assert "observador" in message
    assert "receberá as notificações do GLPI" in message
    assert "usuário ID" not in message
    assert "vínculo" not in message
    assert "https://glpi.local/front/ticket.form.php?id=9274" in message


def test_glpi_event_reader_enriches_linked_user_and_group_names():
    reader = GLPITicketEventReader(FakeLinkedGLPIClient())

    snapshot = reader.read_snapshot(9274)
    linked_user = snapshot.related_items["Ticket_User"][0]
    linked_group = snapshot.related_items["Group_Ticket"][0]

    assert linked_user["linked_user_name"] == "Ana Silva"
    assert linked_user["linked_type_label"] == "observador"
    assert linked_group["linked_group_name"] == "Suporte N2"
    assert linked_group["linked_type_label"] == "responsável pelo atendimento"
