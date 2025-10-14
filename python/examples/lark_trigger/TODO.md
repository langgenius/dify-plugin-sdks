# Lark Trigger Events Implementation Todo List

## IM Events (events/im/)
- [ ] p2p_chat_entered_v1 - Bot enters a P2P chat *(available via lark-oapi 1.4.23)*
- [ ] chat_disbanded_v1 - Chat disbanded notifications *(available via lark-oapi 1.4.23)*
- [ ] p2p_im_chat_member_bot_added_v1 - Bot added to chat *(available via lark-oapi 1.4.23)*
- [ ] p2p_im_chat_member_bot_deleted_v1 - Bot removed from chat *(available via lark-oapi 1.4.23)*
- [x] chat_member_user_added_v1 - Users added to chat
- [x] chat_member_user_removed_v1 - Users removed from chat
- [ ] chat_member_user_withdrawn_v1 - Users withdrew join requests *(available via lark-oapi 1.4.23)*
- [ ] chat_updated_v1 - Chat metadata updated *(available via lark-oapi 1.4.23)*
- [x] message_read_v1 - Message read receipts
- [x] message_reaction_added_v1 - Message reactions added
- [ ] message_reaction_deleted_v1 - Message reactions removed *(available via lark-oapi 1.4.23)*
- [ ] message_recalled_v1 - Messages recalled *(available via lark-oapi 1.4.23)*
- [x] p2p_im_message_receive_v1 - Receive IM messages

## Calendar Events (events/calendar/)
- [x] event_changed_v4 - Calendar event changes
- [x] calendar_acl_created_v4 - Calendar permissions granted
- [x] calendar_acl_deleted_v4 - Calendar permissions revoked
- [ ] calendar_changed_v4 - Calendar metadata updated *(available via lark-oapi 1.4.23)*

## Approval Events (events/approval/)
- [x] approval_updated_v4 - Approval status changes
- [ ] approval_task_updated_v4 - Approval task updates *(pending SDK support in lark-oapi 1.4.23)*

## Drive Events (events/drive/)
- [x] file_created_v1 - File created in folder
- [x] file_deleted_v1 - File deleted
- [x] file_edit_v1 - File edited
- [x] file_permission_member_added_v1 - File sharing permissions added
- [x] file_permission_member_removed_v1 - File sharing permissions removed
- [ ] file_permission_member_applied_v1 - Sharing permission requests *(available via lark-oapi 1.4.23)*
- [ ] file_read_v1 - File viewed *(available via lark-oapi 1.4.23)*
- [ ] file_title_updated_v1 - File renamed *(available via lark-oapi 1.4.23)*
- [ ] file_trashed_v1 - File moved to trash *(available via lark-oapi 1.4.23)*
- [ ] file_bitable_record_changed_v1 - Bitable record changed *(available via lark-oapi 1.4.23)*
- [ ] file_bitable_field_changed_v1 - Bitable field schema changed *(available via lark-oapi 1.4.23)*

## Contact Events (events/contact/)
- [x] user_created_v3 - New employee onboarded
- [x] user_updated_v3 - Employee information updated
- [ ] user_deleted_v3 - Employee removed *(available via lark-oapi 1.4.23)*
- [x] department_created_v3 - New department created
- [x] department_updated_v3 - Department information updated
- [x] department_deleted_v3 - Department removed
- [ ] custom_attr_event_updated_v3 - Custom contact attribute changed *(available via lark-oapi 1.4.23)*
- [ ] employee_type_enum_created_v3 - Employee type enumerations created *(available via lark-oapi 1.4.23)*
- [ ] employee_type_enum_actived_v3 - Employee type enumeration activated *(available via lark-oapi 1.4.23)*
- [ ] employee_type_enum_deactivated_v3 - Employee type enumeration deactivated *(available via lark-oapi 1.4.23)*
- [ ] employee_type_enum_deleted_v3 - Employee type enumeration removed *(available via lark-oapi 1.4.23)*
- [ ] employee_type_enum_updated_v3 - Employee type enumeration updated *(available via lark-oapi 1.4.23)*
- [ ] scope_updated_v3 - Contact visibility scope updated *(available via lark-oapi 1.4.23)*

## Hire Events (events/hire/)
- [ ] application_deleted_v1 - Application removed *(available via lark-oapi 1.4.23)*
- [ ] application_stage_changed_v1 - Application stage changed *(available via lark-oapi 1.4.23)*
- [ ] eco_account_created_v1 - Eco account created *(available via lark-oapi 1.4.23)*
- [ ] eco_background_check_canceled_v1 - Background check cancelled *(available via lark-oapi 1.4.23)*
- [ ] eco_background_check_created_v1 - Background check initiated *(available via lark-oapi 1.4.23)*
- [ ] eco_exam_created_v1 - Exam scheduled *(available via lark-oapi 1.4.23)*
- [ ] ehr_import_task_imported_v1 - Offer import task completed *(available via lark-oapi 1.4.23)*
- [ ] ehr_import_task_for_internship_offer_imported_v1 - Internship offer import completed *(available via lark-oapi 1.4.23)*
- [ ] offer_status_changed_v1 - Offer status changed *(available via lark-oapi 1.4.23)*
- [ ] referral_account_assets_update_v1 - Referral assets updated *(available via lark-oapi 1.4.23)*
- [ ] talent_deleted_v1 - Talent profile deleted *(available via lark-oapi 1.4.23)*
- [ ] talent_tag_subscription_v1 - Talent tag subscriptions updated *(available via lark-oapi 1.4.23)*
- [ ] application_created_v1 - Job application submitted *(not exposed in lark-oapi 1.4.23)*
- [ ] application_status_changed_v1 - Application status updated *(not exposed in lark-oapi 1.4.23)*
- [ ] interview_created_v1 - Interview scheduled *(not exposed in lark-oapi 1.4.23)*

## Core HR Events (events/corehr/)
- [ ] approval_groups_updated_v2 - Approval group configuration updated *(available via lark-oapi 1.4.23)*
- [ ] common_data_meta_data_updated_v1 - Core HR metadata definition changed *(available via lark-oapi 1.4.23)*
- [ ] company_created_v2 - Company entity created *(available via lark-oapi 1.4.23)*
- [ ] company_deleted_v2 - Company entity deleted *(available via lark-oapi 1.4.23)*
- [ ] company_updated_v2 - Company entity updated *(available via lark-oapi 1.4.23)*
- [ ] contract_created_v1 - Employment contract created *(available via lark-oapi 1.4.23)*
- [ ] contract_deleted_v1 - Employment contract deleted *(available via lark-oapi 1.4.23)*
- [ ] contract_updated_v1 - Employment contract updated *(available via lark-oapi 1.4.23)*
- [ ] cost_center_created_v2 - Cost center created *(available via lark-oapi 1.4.23)*
- [ ] cost_center_deleted_v2 - Cost center deleted *(available via lark-oapi 1.4.23)*
- [ ] cost_center_updated_v2 - Cost center updated *(available via lark-oapi 1.4.23)*
- [ ] custom_org_created_v2 - Custom organization node created *(available via lark-oapi 1.4.23)*
- [ ] custom_org_deleted_v2 - Custom organization node deleted *(available via lark-oapi 1.4.23)*
- [ ] custom_org_updated_v2 - Custom organization node updated *(available via lark-oapi 1.4.23)*
- [ ] department_created_v1 - Department created *(available via lark-oapi 1.4.23)*
- [ ] department_created_v2 - Department created (v2) *(available via lark-oapi 1.4.23)*
- [ ] department_deleted_v1 - Department deleted *(available via lark-oapi 1.4.23)*
- [ ] department_updated_v1 - Department updated *(available via lark-oapi 1.4.23)*
- [ ] department_updated_v2 - Department updated (v2) *(available via lark-oapi 1.4.23)*
- [ ] employee_domain_event_v2 - Employee domain change event *(available via lark-oapi 1.4.23)*
- [ ] employment_converted_v1 - Employment converted *(available via lark-oapi 1.4.23)*
- [ ] employment_created_v1 - Employment created *(available via lark-oapi 1.4.23)*
- [ ] employment_deleted_v1 - Employment deleted *(available via lark-oapi 1.4.23)*
- [ ] employment_resigned_v1 - Employment resigned *(available via lark-oapi 1.4.23)*
- [ ] employment_updated_v1 - Employment updated *(available via lark-oapi 1.4.23)*
- [ ] job_change_status_updated_v2 - Job change status updated *(available via lark-oapi 1.4.23)*
- [ ] job_change_updated_v1 - Job change updated (v1) *(available via lark-oapi 1.4.23)*
- [ ] job_change_updated_v2 - Job change updated (v2) *(available via lark-oapi 1.4.23)*
- [ ] job_created_v1 - Job created *(available via lark-oapi 1.4.23)*
- [ ] job_data_changed_v1 - Job data changed *(available via lark-oapi 1.4.23)*
- [ ] job_data_created_v1 - Job data created *(available via lark-oapi 1.4.23)*
- [ ] job_data_deleted_v1 - Job data deleted *(available via lark-oapi 1.4.23)*
- [ ] job_data_employed_v1 - Job data marked employed *(available via lark-oapi 1.4.23)*
- [ ] job_data_updated_v1 - Job data updated *(available via lark-oapi 1.4.23)*
- [ ] job_deleted_v1 - Job deleted *(available via lark-oapi 1.4.23)*
- [ ] job_family_created_v2 - Job family created *(available via lark-oapi 1.4.23)*
- [ ] job_family_deleted_v2 - Job family deleted *(available via lark-oapi 1.4.23)*
- [ ] job_family_updated_v2 - Job family updated *(available via lark-oapi 1.4.23)*
- [ ] job_grade_created_v2 - Job grade created *(available via lark-oapi 1.4.23)*
- [ ] job_grade_deleted_v2 - Job grade deleted *(available via lark-oapi 1.4.23)*
- [ ] job_grade_updated_v2 - Job grade updated *(available via lark-oapi 1.4.23)*
- [ ] job_level_created_v2 - Job level created *(available via lark-oapi 1.4.23)*
- [ ] job_level_deleted_v2 - Job level deleted *(available via lark-oapi 1.4.23)*
- [ ] job_level_updated_v2 - Job level updated *(available via lark-oapi 1.4.23)*
- [ ] job_updated_v1 - Job updated *(available via lark-oapi 1.4.23)*
- [ ] location_created_v2 - Location created *(available via lark-oapi 1.4.23)*
- [ ] location_deleted_v2 - Location deleted *(available via lark-oapi 1.4.23)*
- [ ] location_updated_v2 - Location updated *(available via lark-oapi 1.4.23)*
- [ ] offboarding_checklist_updated_v2 - Offboarding checklist updated *(available via lark-oapi 1.4.23)*
- [ ] offboarding_status_updated_v2 - Offboarding status updated *(available via lark-oapi 1.4.23)*
- [ ] offboarding_updated_v1 - Offboarding updated *(available via lark-oapi 1.4.23)*
- [ ] offboarding_updated_v2 - Offboarding updated (v2) *(available via lark-oapi 1.4.23)*
- [ ] org_role_authorization_updated_v1 - Org role authorization updated *(available via lark-oapi 1.4.23)*
- [ ] pathway_created_v2 - Pathway created *(available via lark-oapi 1.4.23)*
- [ ] pathway_deleted_v2 - Pathway deleted *(available via lark-oapi 1.4.23)*
- [ ] pathway_updated_v2 - Pathway updated *(available via lark-oapi 1.4.23)*
- [ ] person_created_v1 - Person created *(available via lark-oapi 1.4.23)*
- [ ] person_deleted_v1 - Person deleted *(available via lark-oapi 1.4.23)*
- [ ] person_updated_v1 - Person updated *(available via lark-oapi 1.4.23)*
- [ ] pre_hire_onboarding_task_changed_v2 - Pre-hire onboarding task changed *(available via lark-oapi 1.4.23)*
- [ ] pre_hire_updated_v1 - Pre-hire record updated *(available via lark-oapi 1.4.23)*
- [ ] probation_updated_v2 - Probation data updated *(available via lark-oapi 1.4.23)*
- [ ] process_approver_updated_v2 - Process approver updated *(available via lark-oapi 1.4.23)*
- [ ] process_cc_updated_v2 - Process CC list updated *(available via lark-oapi 1.4.23)*
- [ ] process_node_updated_v2 - Process node updated *(available via lark-oapi 1.4.23)*
- [ ] process_status_update_v2 - Process status updated *(available via lark-oapi 1.4.23)*
- [ ] process_updated_v2 - Process definition updated *(available via lark-oapi 1.4.23)*

## Meeting Events (events/meeting/)
- [ ] meeting_room_created_v1 - Meeting room booked *(not available in lark-oapi 1.4.23)*
- [ ] meeting_room_deleted_v1 - Meeting room cancelled *(not available in lark-oapi 1.4.23)*
- [ ] meeting_room_status_changed_v1 - Meeting room status changed *(not available in lark-oapi 1.4.23)*
- [ ] meeting_room_updated_v1 - Meeting room updated *(available via lark-oapi 1.4.23)*

## Task Events (events/task/)
- [ ] task_task_comment_updated_v1 - Task comment updated *(available via lark-oapi 1.4.23)*
- [ ] task_task_update_tenant_v1 - Tenant-level task data updated *(available via lark-oapi 1.4.23)*
- [ ] task_task_updated_v1 - Task updated *(available via lark-oapi 1.4.23)*

## Attendance Events (events/attendance/)
- No official attendance events exposed in lark-oapi 1.4.23

## Implementation Summary

### ✅ Completed (19 events implemented)
- IM messaging and membership events (5 events)
- Calendar event and ACL updates (3 events)
- Approval workflow updates (1 event)
- Drive file permissions and lifecycle events (5 events)
- Contact user and department lifecycle events (5 events)

### 📋 Implementation Guidelines
- Each event handler extracts explicit fields from Lark SDK models (no __dict__)
- Keep integer and boolean types as-is (don't convert to strings)
- Convert complex objects/arrays to JSON strings for Dify Variables compatibility
- Provide human-friendly labels and descriptions in EN/ZH/JA
- Register dispatch handlers in provider/lark.py for each event
- Reference all events in provider/lark.yaml events section

### 🚀 Ready for Production
All implemented events have been:
- Properly typed with correct data types
- Registered with dispatch handlers
- Referenced in provider configuration
- Tested for type safety
