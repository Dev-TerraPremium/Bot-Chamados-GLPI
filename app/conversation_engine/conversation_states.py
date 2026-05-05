from enum import Enum


class ConversationState(str, Enum):
    MAIN_MENU = "main_menu"
    CATEGORY_ASSIGNMENT_CONFIRMATION = "category_assignment_confirmation"
    CATEGORY_SELECTION = "category_selection"
    OTHER_CATEGORY_TEXT = "other_category_text"
    OTHER_CATEGORY_CONFIRMATION = "other_category_confirmation"
    DESCRIPTION_COLLECTION = "description_collection"
    DESCRIPTION_REVIEW = "description_review"
    IMPACT_SELECTION = "impact_selection"
    LOCATION_COLLECTION = "location_collection"
    EVIDENCE_DECISION = "evidence_decision"
    EVIDENCE_COLLECTION = "evidence_collection"
    FINAL_CONFIRMATION = "final_confirmation"
    QUERY_MENU = "query_menu"
    QUERY_TICKET_NUMBER = "query_ticket_number"
    COMPLEMENT_TICKET_NUMBER = "complement_ticket_number"
    COMPLEMENT_TEXT_COLLECTION = "complement_text_collection"
    COMPLEMENT_REVIEW = "complement_review"
    EXITED = "exited"
