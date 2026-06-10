import fakeredis

from app.application_config.settings import AppSettings
from app.ticket_notifications import integration as notification_integration
from app.ticket_notifications.event_detector import TicketEventDetector
from app.ticket_notifications.event_reader import GLPITicketEventReader
from app.ticket_notifications.event_store import TicketNotificationStore
from app.glpi_integration_reserved.glpi_future_real_client import GLPIClientError
from app.ticket_notifications.message_renderer import TicketNotificationMessageRenderer
from app.ticket_notifications.models import TicketActivitySnapshot, TicketEvent, WatchedTicket
from app.ticket_notifications.pipeline import TicketNotificationPipeline
from app.ticket_notifications.backfill import TicketNotificationBackfillService
from app.ticket_notifications.metrics_recorder import NotificationMetricsRecorder
from app.ticket_domain.ticket_models import TicketCreated


class FakeReader:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)

    def read_snapshot(self, ticket_id: int):
        return self.snapshots.pop(0)


class FailingReader:
    def read_snapshot(self, ticket_id: int):
        raise GLPIClientError("GLPI indisponível")


class MissingTicketReader:
    def read_ticket(self, ticket_id: int):
        raise GLPIClientError("Chamado nao encontrado", status_code=404)

    def read_snapshot(self, ticket_id: int, *, ticket=None):
        raise AssertionError("deleted tickets must not read a full snapshot")


class FakeDispatcher:
    def __init__(self):
        self.sent = []

    def send_message(self, phone: str, message: str):
        self.sent.append((phone, message))

        class Result:
            ok = True

        return Result()


class FakeTeamsDispatcher:
    def __init__(self):
        self.sent = []

    def send_ticket_update(self, channel_identifier: str, *, ticket_id: int, message: str):
        self.sent.append((channel_identifier, ticket_id, message))

        class Result:
            ok = True

        return Result()


class FakeGLPIClient:
    def __init__(self):
        self.related_calls = []

    def get_item(self, itemtype: str, item_id: int):
        if itemtype == "User":
            return {"id": item_id, "firstname": "Ana", "realname": "Silva", "name": "asilva"}
        if itemtype == "Group":
            return {"id": item_id, "name": "Suporte N2"}
        return {"id": item_id, "status": 2, "name": "Chamado teste"}

    def get_ticket_related_items(self, ticket_id: int, itemtype: str):
        self.related_calls.append((ticket_id, itemtype))
        if itemtype == "ITILFollowup":
            return {
                "items": [
                    {
                        "id": 10,
                        "content": "<p>Tecnico pediu mais detalhes.</p>",
                        "date_creation": "2026-05-11 12:00:00",
                        "is_private": 0,
                    }
                ]
            }
        return {"items": []}


class FlakyRelatedGLPIClient:
    def __init__(self):
        self.fail_itemtypes = set()

    def get_item(self, itemtype: str, item_id: int):
        if itemtype == "Ticket":
            return {"id": item_id, "status": 2, "priority": 3, "name": "Chamado teste"}
        if itemtype == "User":
            return {"id": item_id, "firstname": "Ana", "realname": "Silva"}
        if itemtype == "Group":
            return {"id": item_id, "name": "Suporte N2"}
        return {"id": item_id}

    def get_ticket_related_items(self, ticket_id: int, itemtype: str):
        if itemtype in self.fail_itemtypes:
            raise GLPIClientError(f"Falha temporaria em {itemtype}")
        if itemtype == "Ticket_User":
            return {"items": [{"id": 23896, "users_id": 266, "type": 1}]}
        if itemtype == "Group_Ticket":
            return {"items": [{"id": 14312, "groups_id": 28, "type": 2}]}
        return {"items": []}


class FakeBackfillGLPIClient:
    def __init__(self, tickets):
        self.tickets = tickets
        self.calls = []

    def get_my_tickets(self, user_id: int):
        self.calls.append(user_id)
        return list(self.tickets)


class MappingReader:
    def __init__(self, snapshots_by_ticket_id):
        self.snapshots_by_ticket_id = snapshots_by_ticket_id
        self.ticket_reads = []
        self.snapshot_reads = []

    def read_ticket(self, ticket_id: int):
        self.ticket_reads.append(ticket_id)
        snapshots = self.snapshots_by_ticket_id[ticket_id]
        return snapshots[min(len(self.snapshot_reads), len(snapshots) - 1)].ticket

    def read_snapshot(self, ticket_id: int, *, ticket=None):
        self.snapshot_reads.append(ticket_id)
        snapshots = self.snapshots_by_ticket_id[ticket_id]
        index = min(self.snapshot_reads.count(ticket_id) - 1, len(snapshots) - 1)
        snapshot = snapshots[index]
        if ticket is None:
            return snapshot
        return TicketActivitySnapshot(
            ticket_id=snapshot.ticket_id,
            ticket=ticket,
            related_items=snapshot.related_items,
        )


def snapshot_with_followups(*followups):
    return TicketActivitySnapshot(
        ticket_id=9145,
        ticket={"id": 9145, "status": 2, "priority": 3, "name": "Chamado teste"},
        related_items={
            "ITILFollowup": list(followups),
            "ITILSolution": [],
            "TicketTask": [],
            "TicketValidation": [],
            "Document_Item": [],
            "Ticket_User": [],
            "Group_Ticket": [],
        },
    )


def snapshot_with_status(ticket_id: int, status: int, *followups):
    snapshot = snapshot_with_followups(*followups)
    return TicketActivitySnapshot(
        ticket_id=ticket_id,
        ticket={
            **snapshot.ticket,
            "id": ticket_id,
            "status": status,
            "name": f"Chamado {ticket_id}",
        },
        related_items=snapshot.related_items,
    )


def snapshot_with_ticket_fields(ticket_id: int = 9145, **fields):
    snapshot = snapshot_with_followups()
    return TicketActivitySnapshot(
        ticket_id=ticket_id,
        ticket={
            **snapshot.ticket,
            "id": ticket_id,
            **fields,
        },
        related_items=snapshot.related_items,
    )


def snapshot_with_related_items(
    ticket_id: int = 9145,
    *,
    ticket_fields: dict | None = None,
    related_items: dict | None = None,
):
    snapshot = snapshot_with_ticket_fields(ticket_id, **(ticket_fields or {}))
    return TicketActivitySnapshot(
        ticket_id=ticket_id,
        ticket=snapshot.ticket,
        related_items={
            **snapshot.related_items,
            **(related_items or {}),
        },
    )


def deleted_snapshot(ticket_id: int):
    snapshot = snapshot_with_status(ticket_id, 2)
    return TicketActivitySnapshot(
        ticket_id=ticket_id,
        ticket={**snapshot.ticket, "is_deleted": 1},
        related_items=snapshot.related_items,
    )


def test_event_detector_creates_baseline_then_detects_new_followup_once():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    detector = TicketEventDetector(store)

    baseline = snapshot_with_followups()
    assert detector.detect_new_events(baseline) == []

    followup = {
        "id": 99,
        "content": "<p>Estamos analisando o equipamento.</p>",
        "date_creation": "2026-05-11 12:30:00",
        "is_private": 0,
    }
    first_detection = detector.detect_new_events(snapshot_with_followups(followup))
    second_detection = detector.detect_new_events(snapshot_with_followups(followup))

    assert len(first_detection) == 1
    assert first_detection[0].event_type == "followup_added"
    assert "Estamos analisando" in first_detection[0].new_value
    assert second_detection == []


def test_event_detector_does_not_reemit_old_related_items_after_recent_event_ttl_expires():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client, recent_events_ttl_seconds=1)
    detector = TicketEventDetector(store)
    followup = {
        "id": 99,
        "content": "<p>Evento antigo.</p>",
        "date_creation": "2026-05-11 12:30:00",
        "is_private": 0,
    }

    detector.detect_new_events(snapshot_with_followups())
    first_detection = detector.detect_new_events(snapshot_with_followups(followup))
    for key in list(redis_client.scan_iter("ticket_notifications:event:*")):
        redis_client.delete(key)
    second_detection = detector.detect_new_events(snapshot_with_followups(followup))

    assert len(first_detection) == 1
    assert second_detection == []


def test_event_detector_ignores_related_item_date_mod_only_change():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    detector = TicketEventDetector(store)

    detector.detect_new_events(
        snapshot_with_followups(
            {
                "id": 99,
                "content": "<p>Mesmo conteúdo.</p>",
                "date_mod": "2026-05-11 12:30:00",
                "is_private": 0,
            }
        )
    )
    detection = detector.detect_new_events(
        snapshot_with_followups(
            {
                "id": 99,
                "content": "<p>Mesmo conteúdo.</p>",
                "date_mod": "2026-05-11 13:30:00",
                "is_private": 0,
            }
        )
    )

    assert detection == []


def test_pipeline_related_read_failure_does_not_overwrite_snapshot_or_send_events():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    client = FlakyRelatedGLPIClient()
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_retry_delay_seconds=0,
        ),
        redis_client=redis_client,
        event_reader=GLPITicketEventReader(client),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    baseline_snapshot = store.get_snapshot(9145)
    client.fail_itemtypes.add("Group_Ticket")

    summary = pipeline.run_once()

    assert summary["failed"] == 1
    assert summary["captured"] == 0
    assert summary["rescheduled"] == 1
    assert store.get_snapshot(9145) == baseline_snapshot
    assert dispatcher.sent == []


def test_pipeline_does_not_reemit_old_related_items_after_failed_read_recovers_post_ttl():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client, recent_events_ttl_seconds=1)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    client = FlakyRelatedGLPIClient()
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_retry_delay_seconds=0,
        ),
        redis_client=redis_client,
        event_reader=GLPITicketEventReader(client),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    for key in list(redis_client.scan_iter("ticket_notifications:event:*")):
        redis_client.delete(key)

    client.fail_itemtypes.add("Group_Ticket")
    failed_summary = pipeline.run_once()
    client.fail_itemtypes.clear()
    recovered_summary = pipeline.run_once()

    assert failed_summary["failed"] == 1
    assert recovered_summary["captured"] == 0
    assert dispatcher.sent == []


def test_pipeline_notifies_private_events_by_default():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    watched = WatchedTicket(
        ticket_id=9145,
        requester_phone="556699990980",
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        category_name="Sistemas",
        title="Erro no sistema",
        location="Matriz",
        created_at="2026-05-11 12:00:00",
    )
    store.watch_ticket(watched)
    private_followup = {
        "id": 100,
        "content": "Atualizacao interna configurada para notificar.",
        "date_creation": "2026-05-11 12:31:00",
        "is_private": 1,
    }
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_include_private_events=True,
        ),
        redis_client=redis_client,
        event_reader=FakeReader(
            [
                snapshot_with_followups(),
                snapshot_with_followups(private_followup),
            ]
        ),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    summary = pipeline.run_once()

    assert summary["sent"] == 1
    assert dispatcher.sent[0][0] == "556699990980"
    assert "Atualizacao interna" in dispatcher.sent[0][1]


def test_pipeline_can_ignore_private_events_by_env():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    private_followup = {
        "id": 101,
        "content": "Nao enviar ao usuario.",
        "date_creation": "2026-05-11 12:32:00",
        "is_private": 1,
    }
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_include_private_events=False,
        ),
        redis_client=redis_client,
        event_reader=FakeReader(
            [
                snapshot_with_followups(),
                snapshot_with_followups(private_followup),
            ]
        ),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    summary = pipeline.run_once()

    assert summary["ignored"] == 1
    assert dispatcher.sent == []


def test_pipeline_suppresses_selected_notification_events_by_default():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
        ),
        redis_client=redis_client,
        event_reader=FakeReader(
            [
                snapshot_with_ticket_fields(
                    urgency=2,
                    itilcategories_id=651,
                    takeintoaccountdate="",
                    begin_waiting_date="",
                ),
                snapshot_with_related_items(
                    ticket_fields={
                        "urgency": 4,
                        "itilcategories_id": 644,
                        "takeintoaccountdate": "2026-06-09 16:51:19",
                        "begin_waiting_date": "2026-06-09 16:53:42",
                    },
                    related_items={
                        "TicketTask": [
                            {
                                "id": 501,
                                "content": "Feito.",
                                "date_creation": "2026-06-09 16:52:00",
                            }
                        ],
                        "Group_Ticket": [
                            {
                                "id": 502,
                                "groups_id": 28,
                                "linked_group_name": "ROO > Corp. TI > Sistemas",
                                "type": 2,
                                "date_creation": "2026-06-09 16:52:30",
                            }
                        ],
                    },
                ),
            ]
        ),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    summary = pipeline.run_once()

    assert summary["captured"] == 6
    assert summary["suppressed"] == 6
    assert summary["ignored"] == 6
    assert summary["sent"] == 0
    assert dispatcher.sent == []


def test_pipeline_reenables_suppressed_notification_events_when_env_list_is_empty():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_disabled_event_types="",
        ),
        redis_client=redis_client,
        event_reader=FakeReader(
            [
                snapshot_with_ticket_fields(
                    urgency=2,
                    itilcategories_id=651,
                    takeintoaccountdate="",
                    begin_waiting_date="",
                ),
                snapshot_with_related_items(
                    ticket_fields={
                        "urgency": 4,
                        "itilcategories_id": 644,
                        "takeintoaccountdate": "2026-06-09 16:51:19",
                        "begin_waiting_date": "2026-06-09 16:53:42",
                    },
                    related_items={
                        "TicketTask": [
                            {
                                "id": 501,
                                "content": "Feito.",
                                "date_creation": "2026-06-09 16:52:00",
                            }
                        ],
                        "Group_Ticket": [
                            {
                                "id": 502,
                                "groups_id": 28,
                                "linked_group_name": "ROO > Corp. TI > Sistemas",
                                "type": 2,
                                "date_creation": "2026-06-09 16:52:30",
                            }
                        ],
                    },
                ),
            ]
        ),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    summary = pipeline.run_once()

    assert summary["captured"] == 6
    assert summary["suppressed"] == 0
    assert summary["sent"] == 6
    assert len(dispatcher.sent) == 6


def test_pipeline_sends_ticket_updates_to_internal_numbers():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    followup = {
        "id": 103,
        "content": "Tecnico atualizou o chamado.",
        "date_creation": "2026-05-11 12:34:00",
        "is_private": 0,
    }
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_internal_update_numbers="6699990001,6699990000",
        ),
        redis_client=redis_client,
        event_reader=FakeReader(
            [
                snapshot_with_followups(),
                snapshot_with_followups(followup),
            ]
        ),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    summary = pipeline.run_once()

    assert summary["sent"] == 1
    assert summary["sent_internal"] == 2
    assert [phone for phone, _message in dispatcher.sent] == [
        "556699990980",
        "6699990001",
        "6699990000",
    ]
    assert "de *Pedro Torres*" in dispatcher.sent[1][1]


def test_pipeline_deduplicates_internal_number_when_it_matches_requester():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    followup = {
        "id": 104,
        "content": "Atualizacao unica.",
        "date_creation": "2026-05-11 12:35:00",
        "is_private": 0,
    }
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_internal_update_numbers="6699990980",
        ),
        redis_client=redis_client,
        event_reader=FakeReader(
            [
                snapshot_with_followups(),
                snapshot_with_followups(followup),
            ]
        ),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    summary = pipeline.run_once()

    assert summary["sent"] == 1
    assert summary["sent_internal"] == 0
    assert len(dispatcher.sent) == 1


def test_pipeline_sends_throttled_error_alerts():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_retry_delay_seconds=0,
            ticket_notification_error_alert_numbers="6699990980",
            ticket_notification_error_alert_cooldown_seconds=300,
            ticket_notification_error_alert_consecutive_failures=1,
        ),
        redis_client=redis_client,
        event_reader=FailingReader(),
        dispatcher=dispatcher,
        store=store,
    )

    first_summary = pipeline.run_once()
    second_summary = pipeline.run_once()

    assert first_summary["failed"] == 1
    assert second_summary["failed"] == 1
    assert len(dispatcher.sent) == 1
    assert "Falha no monitoramento de chamados" in dispatcher.sent[0][1]


def test_pipeline_waits_for_consecutive_glpi_failures_before_alerting():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_retry_delay_seconds=0,
            ticket_notification_error_alert_numbers="6699990980",
            ticket_notification_error_alert_cooldown_seconds=0,
            ticket_notification_error_alert_consecutive_failures=3,
        ),
        redis_client=redis_client,
        event_reader=FailingReader(),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()
    pipeline.run_once()
    assert dispatcher.sent == []

    pipeline.run_once()
    assert len(dispatcher.sent) == 1


def test_pipeline_glpi_error_alerts_use_global_cooldown_across_tickets():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    for ticket_id in (9145, 9146):
        store.watch_ticket(
            WatchedTicket(
                ticket_id=ticket_id,
                requester_phone="556699990980",
                requester_name="Pedro Torres",
                requester_login="pedro.torres",
                category_name="Sistemas",
                title=f"Erro no sistema {ticket_id}",
                location="Matriz",
                created_at="2026-05-11 12:00:00",
            )
        )
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
            ticket_notification_retry_delay_seconds=0,
            ticket_notification_batch_size=2,
            ticket_notification_error_alert_numbers="6699990980",
            ticket_notification_error_alert_cooldown_seconds=300,
            ticket_notification_error_alert_consecutive_failures=1,
        ),
        redis_client=redis_client,
        event_reader=FailingReader(),
        dispatcher=dispatcher,
        store=store,
    )

    pipeline.run_once()

    assert len(dispatcher.sent) == 1


def test_pipeline_sends_ticket_updates_to_teams_channel():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9274,
            requester_phone="",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
            channel="teams",
            channel_identifier="aad-user-id",
        )
    )
    followup = {
        "id": 105,
        "content": "Tecnico atualizou o chamado.",
        "date_creation": "2026-05-11 12:36:00",
        "is_private": 0,
    }
    teams_dispatcher = FakeTeamsDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=0,
        ),
        redis_client=redis_client,
        event_reader=FakeReader(
            [
                snapshot_with_status(9274, 2),
                snapshot_with_status(9274, 2, followup),
            ]
        ),
        dispatcher=FakeDispatcher(),
        store=store,
        teams_dispatcher=teams_dispatcher,
    )

    pipeline.run_once()
    summary = pipeline.run_once()

    assert summary["sent"] == 1
    assert teams_dispatcher.sent[0][0] == "aad-user-id"
    assert teams_dispatcher.sent[0][1] == 9274
    assert "Tecnico atualizou" in teams_dispatcher.sent[0][2]


def test_store_rotates_due_watched_tickets_without_starving_later_items():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    for ticket_id in (1, 2, 3):
        store.watch_ticket(
            WatchedTicket(
                ticket_id=ticket_id,
                requester_phone=f"55669999098{ticket_id}",
                requester_name="Pedro Torres",
                requester_login="pedro.torres",
                category_name="Sistemas",
                title=f"Chamado {ticket_id}",
                location="Matriz",
                created_at="2026-05-11 12:00:00",
            ),
            next_poll_at=100,
        )

    first_batch = store.list_watched_tickets(2, now=100)
    assert [ticket.ticket_id for ticket in first_batch] == [1, 2]

    store.reschedule_ticket(1, delay_seconds=60, now=100)
    store.reschedule_ticket(2, delay_seconds=60, now=100)
    second_batch = store.list_watched_tickets(2, now=100)

    assert [ticket.ticket_id for ticket in second_batch] == [3]


def test_pipeline_stops_watching_terminal_tickets_without_related_reads():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    reader = MappingReader({9145: [snapshot_with_status(9145, 5)]})
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
        ),
        redis_client=redis_client,
        event_reader=reader,
        dispatcher=FakeDispatcher(),
        store=store,
    )

    summary = pipeline.run_once()

    assert summary["stopped"] == 1
    assert not store.is_watching(9145)
    assert reader.ticket_reads == [9145]
    assert reader.snapshot_reads == []


def test_pipeline_stops_watching_deleted_tickets_without_related_reads():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    reader = MappingReader({9145: [deleted_snapshot(9145)]})
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
        ),
        redis_client=redis_client,
        event_reader=reader,
        dispatcher=FakeDispatcher(),
        store=store,
    )

    summary = pipeline.run_once()

    assert summary["stopped"] == 1
    assert not store.is_watching(9145)
    assert reader.ticket_reads == [9145]
    assert reader.snapshot_reads == []


def test_pipeline_stops_watching_missing_ticket_without_retrying():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        )
    )
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
        ),
        redis_client=redis_client,
        event_reader=MissingTicketReader(),
        dispatcher=FakeDispatcher(),
        store=store,
    )

    summary = pipeline.run_once()

    assert summary["stopped"] == 1
    assert summary["failed"] == 0
    assert summary["rescheduled"] == 0
    assert not store.is_watching(9145)


def test_pipeline_reschedules_failed_reads_so_one_bad_ticket_does_not_starve_queue():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TicketNotificationStore(redis_client)
    store.watch_ticket(
        WatchedTicket(
            ticket_id=9145,
            requester_phone="556699990980",
            requester_name="Pedro Torres",
            requester_login="pedro.torres",
            category_name="Sistemas",
            title="Erro no sistema",
            location="Matriz",
            created_at="2026-05-11 12:00:00",
        ),
        next_poll_at=100,
    )
    dispatcher = FakeDispatcher()
    pipeline = TicketNotificationPipeline(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_poll_interval_seconds=30,
            ticket_notification_error_alert_numbers="6699990980",
            ticket_notification_error_alert_cooldown_seconds=0,
            ticket_notification_error_alert_consecutive_failures=1,
        ),
        redis_client=redis_client,
        event_reader=FailingReader(),
        dispatcher=dispatcher,
        store=store,
    )

    summary = pipeline.run_once()

    assert summary["failed"] == 1
    assert summary["rescheduled"] == 1
    assert store.list_watched_tickets(1, now=100) == []
    assert dispatcher.sent


def test_backfill_registers_active_user_tickets_with_baseline_only():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    redis_client.set(
        "channel_link:whatsapp:66999990980",
        (
            '{"channel":"whatsapp","channel_identifier":"66999990980",'
            '"status":"active","glpi_user_id":266,"glpi_login":"pedro.torres",'
            '"display_name":"Pedro"}'
        ),
    )
    store = TicketNotificationStore(redis_client)
    ticket = TicketCreated(
        ticket_number=9145,
        title="Erro no sistema",
        status="Em atendimento",
        severity="Baixa",
        description="Descricao",
        category_name="Sistemas",
        requester_login="pedro.torres",
        glpi_user_id=266,
        channel="whatsapp",
        location="Matriz",
        impact_label="Simples",
        evidence="",
        opening_mode="Abertura assistida",
        created_at="2026-05-11 12:00:00",
    )
    reader = MappingReader(
        {
            9145: [
                snapshot_with_followups(
                    {
                        "id": 10,
                        "content": "Evento antigo vira baseline.",
                        "date_creation": "2026-05-11 12:30:00",
                        "is_private": 0,
                    }
                )
            ]
        }
    )
    detector = TicketEventDetector(store)
    service = TicketNotificationBackfillService(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_backfill_interval_seconds=60,
        ),
        redis_client=redis_client,
        glpi_client=FakeBackfillGLPIClient([ticket]),
        store=store,
        event_reader=reader,
        detector=detector,
        metrics=NotificationMetricsRecorder(redis_client),
    )

    summary = service.run_if_due()

    assert summary["users"] == 1
    assert summary["tickets_added"] == 1
    assert store.is_watching(9145)
    assert detector.detect_new_events(reader.read_snapshot(9145)) == []


def test_backfill_rejects_tickets_when_related_snapshot_is_incomplete():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    redis_client.set(
        "channel_link:whatsapp:66999990980",
        (
            '{"channel":"whatsapp","channel_identifier":"66999990980",'
            '"status":"active","glpi_user_id":266,"glpi_login":"pedro.torres",'
            '"display_name":"Pedro"}'
        ),
    )
    store = TicketNotificationStore(redis_client)
    ticket = TicketCreated(
        ticket_number=9145,
        title="Erro no sistema",
        status="Em atendimento",
        severity="Baixa",
        description="Descricao",
        category_name="Sistemas",
        requester_login="pedro.torres",
        glpi_user_id=266,
        channel="whatsapp",
        location="Matriz",
        impact_label="Simples",
        evidence="",
        opening_mode="Abertura assistida",
        created_at="2026-05-11 12:00:00",
    )
    client = FlakyRelatedGLPIClient()
    client.fail_itemtypes.add("Group_Ticket")
    service = TicketNotificationBackfillService(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_backfill_interval_seconds=60,
        ),
        redis_client=redis_client,
        glpi_client=FakeBackfillGLPIClient([ticket]),
        store=store,
        event_reader=GLPITicketEventReader(client),
        detector=TicketEventDetector(store),
        metrics=NotificationMetricsRecorder(redis_client),
    )

    summary = service.run_if_due()

    assert summary["failed"] == 1
    assert summary["tickets_added"] == 0
    assert not store.is_watching(9145)


def test_backfill_removes_terminal_tickets_that_are_still_watched():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    redis_client.set(
        "channel_link:whatsapp:66999990980",
        (
            '{"channel":"whatsapp","channel_identifier":"66999990980",'
            '"status":"active","glpi_user_id":266,"glpi_login":"pedro.torres",'
            '"display_name":"Pedro"}'
        ),
    )
    store = TicketNotificationStore(redis_client)
    tickets = []
    for ticket_id, status in ((9301, "Fechado"), (9302, "Solucionado"), (9303, "Deletado")):
        store.watch_ticket(
            WatchedTicket(
                ticket_id=ticket_id,
                requester_phone="66999990980",
                requester_name="Pedro",
                requester_login="pedro.torres",
                category_name="Sistemas",
                title=f"Chamado {status}",
                location="Matriz",
                created_at="2026-05-11 12:00:00",
            )
        )
        tickets.append(
            TicketCreated(
                ticket_number=ticket_id,
                title=f"Chamado {status}",
                status=status,
                severity="Baixa",
                description="Descricao",
                category_name="Sistemas",
                requester_login="pedro.torres",
                glpi_user_id=266,
                channel="whatsapp",
                location="Matriz",
                impact_label="Simples",
                evidence="",
                opening_mode="Abertura assistida",
                created_at="2026-05-11 12:00:00",
            )
        )
    service = TicketNotificationBackfillService(
        settings=AppSettings(
            state_backend="redis",
            ticket_notifications_enabled=True,
            whatsapp_internal_api_token="token",
            ticket_notification_backfill_interval_seconds=60,
        ),
        redis_client=redis_client,
        glpi_client=FakeBackfillGLPIClient(tickets),
        store=store,
        event_reader=MappingReader({}),
        detector=TicketEventDetector(store),
        metrics=NotificationMetricsRecorder(redis_client),
    )

    service.run_if_due()

    assert not store.is_watching(9301)
    assert not store.is_watching(9302)
    assert not store.is_watching(9303)


def test_internal_open_notification_deduplicates_requester_number(monkeypatch):
    sent = []

    class FakeWhatsAppDispatcher:
        def __init__(self, **kwargs):
            pass

        def send_message(self, phone: str, message: str):
            sent.append((phone, message))

            class Result:
                ok = True

            return Result()

    class FakeMetrics:
        def __init__(self):
            self.names = []

        def increment(self, name: str, value: int = 1):
            self.names.append(name)

    monkeypatch.setattr(
        notification_integration,
        "WhatsAppNotificationDispatcher",
        FakeWhatsAppDispatcher,
    )
    watched = WatchedTicket(
        ticket_id=9145,
        requester_phone="556699990980",
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        category_name="Sistemas",
        title="Erro no sistema",
        location="Matriz",
        created_at="2026-05-11 12:00:00",
    )
    metrics = FakeMetrics()

    notification_integration._send_internal_ticket_opened_notification(
        AppSettings(
            ticket_notification_internal_numbers="6699990980,6699990000",
            whatsapp_internal_api_token="token",
        ),
        watched,
        {"description": "Descricao"},
        metrics,
    )

    assert [phone for phone, _message in sent] == ["6699990000"]
    assert "internal_open_notifications_deduplicated" in metrics.names


def test_glpi_event_reader_maps_related_item_endpoints():
    client = FakeGLPIClient()
    reader = GLPITicketEventReader(client)

    snapshot = reader.read_snapshot(9145)

    assert snapshot.ticket["id"] == 9145
    assert snapshot.related_items["ITILFollowup"][0]["id"] == 10
    assert (9145, "ITILFollowup") in client.related_calls


def test_renderer_uses_natural_language_without_menu_title():
    renderer = TicketNotificationMessageRenderer(
        ticket_url_template="https://glpi.local/front/ticket.form.php?id={ticket_id}"
    )
    watched = WatchedTicket(
        ticket_id=9145,
        requester_phone="556699990980",
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        category_name="Sistemas",
        title="Erro no sistema",
        location="Matriz",
        created_at="2026-05-11 12:00:00",
    )
    event = snapshot_with_followups(
        {
            "id": 102,
            "content": "O tecnico respondeu.",
            "date_creation": "2026-05-11 12:33:00",
        }
    ).related_items["ITILFollowup"][0]

    message = renderer.render_user_message(
        watched,
        TicketEventDetector(TicketNotificationStore(fakeredis.FakeRedis(decode_responses=True))).mapper.events_from_snapshot(
            snapshot_with_followups(event),
            {"ticket": {"status": "2", "priority": "3", "name": "Chamado teste"}},
        )[0],
    )

    assert "chamado *#9145*" in message
    assert "resposta" in message
    assert "https://glpi.local/front/ticket.form.php?id=9145" in message
    assert "Notificacao" not in message


def test_renderer_varies_opening_and_describes_ticket_changes():
    renderer = TicketNotificationMessageRenderer()
    watched = WatchedTicket(
        ticket_id=9155,
        requester_phone="556699990980",
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        category_name="Infraestrutura",
        title="Mouse e teclado",
        location="Rondonópolis",
        created_at="2026-05-11 15:00:00",
    )
    events = [
        TicketEvent(
            ticket_id=9155,
            event_type="ticket_status_changed",
            source_itemtype="Ticket",
            source_id=f"status-{index}",
            occurred_at=f"2026-05-11 15:0{index}:00",
            is_private=False,
            actor="266",
            old_value="novo",
            new_value="em atendimento",
            raw_payload={"field": "status"},
        )
        for index in range(5)
    ]

    messages = [renderer.render_user_message(watched, event) for event in events]

    assert len({message.split(":")[0] for message in messages}) > 1
    assert any(not message.startswith("Pedro,") for message in messages)
    assert all("O *status* mudou de *novo* → *em atendimento*" in message for message in messages)


def test_event_mapper_uses_human_labels_for_glpi_levels():
    detector = TicketEventDetector(TicketNotificationStore(fakeredis.FakeRedis(decode_responses=True)))
    snapshot = TicketActivitySnapshot(
        ticket_id=9274,
        ticket={"id": 9274, "status": 2, "priority": 5, "urgency": 4, "impact": 3},
        related_items={
            "ITILFollowup": [],
            "ITILSolution": [],
            "TicketTask": [],
            "TicketValidation": [],
            "Document_Item": [],
            "Ticket_User": [],
            "Group_Ticket": [],
        },
    )

    events = detector.mapper.events_from_snapshot(
        snapshot,
        {
            "ticket": {
                "status": "1",
                "priority": "2",
                "urgency": "2",
                "impact": "2",
            }
        },
    )
    values = {event.event_type: (event.old_value, event.new_value) for event in events}

    assert values["ticket_priority_changed"] == ("Baixa", "Muito alta")
    assert values["ticket_urgency_changed"] == ("Baixa", "Alta")
    assert values["ticket_impact_changed"] == ("Baixo", "Médio")


def test_renderer_names_linked_person_when_available():
    renderer = TicketNotificationMessageRenderer()
    watched = WatchedTicket(
        ticket_id=9155,
        requester_phone="556699990980",
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        category_name="Infraestrutura",
        title="Mouse e teclado",
        location="Rondonópolis",
        created_at="2026-05-11 15:00:00",
    )
    event = TicketEvent(
        ticket_id=9155,
        event_type="ticket_user_changed",
        source_itemtype="Ticket_User",
        source_id="20",
        occurred_at="2026-05-11 15:10:00",
        is_private=False,
        actor="266",
        old_value="",
        new_value="266",
        raw_payload={"users_id": 266, "name": "Pedro Américo Paletot"},
    )

    message = renderer.render_user_message(watched, event)

    assert "foi vinculada ao chamado" in message
    assert "Pedro Américo Paletot" in message
