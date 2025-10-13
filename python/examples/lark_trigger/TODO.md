# Lark Trigger Events Implementation Todo List

## IM Events (events/im/) ✅
- [x] p2p_im_message_receive_v1 - Receive IM messages
- [x] chat_member_user_added_v1 - Users added to chat
- [x] chat_member_user_removed_v1 - Users removed from chat  
- [x] message_reaction_added_v1 - Message reactions
- [x] message_read_v1 - Message read receipts

## Calendar Events (events/calendar/) ✅
- [x] event_changed_v4 - Calendar event changes
- [ ] calendar_acl_created_v4 - Calendar permissions granted
- [ ] calendar_acl_deleted_v4 - Calendar permissions revoked

## Approval Events (events/approval/) ✅
- [x] approval_updated_v4 - Approval status changes
- [ ] approval_task_updated_v4 - Approval task updates

## Drive Events (events/drive/) 
- [x] file_created_v1 - File created in folder
- [ ] file_deleted_v1 - File deleted
- [ ] file_edit_v1 - File edited
- [ ] file_permission_member_added_v1 - File sharing permissions added
- [ ] file_permission_member_removed_v1 - File sharing permissions removed

## Contact Events (events/contact/) ✅
- [x] user_created_v3 - New employee onboarded
- [ ] user_updated_v3 - Employee information updated  
- [x] department_created_v3 - New department created
- [ ] department_updated_v3 - Department information updated
- [ ] department_deleted_v3 - Department removed

## Hire Events (events/hire/)
- [ ] application_created_v1 - Job application submitted
- [ ] application_status_changed_v1 - Application status updated
- [ ] interview_created_v1 - Interview scheduled
- [ ] offer_status_changed_v1 - Offer status changed

## Core HR Events (events/corehr/)
- [ ] employee_created_v1 - Employee record created
- [ ] employee_updated_v1 - Employee information updated
- [ ] job_change_v1 - Job position changed
- [ ] offboarding_v1 - Employee offboarding

## Meeting Events (events/meeting/)
- [ ] meeting_room_created_v1 - Meeting room booked
- [ ] meeting_room_deleted_v1 - Meeting room cancelled
- [ ] meeting_room_status_changed_v1 - Meeting room status changed

## Task Events (events/task/)
- [ ] task_created_v1 - Task created
- [ ] task_updated_v1 - Task updated
- [ ] task_comment_created_v1 - Task comment added
- [ ] task_completed_v1 - Task marked complete

## Attendance Events (events/attendance/)
- [ ] user_check_in_v1 - Employee check-in
- [ ] user_check_out_v1 - Employee check-out
- [ ] shift_updated_v1 - Work shift updated

## Implementation Summary

### ✅ Completed (10 events implemented)
- All IM messaging events (5 events)
- Calendar event changes (1 event)
- Approval workflow updates (1 event)
- Drive file creation (1 event)
- Contact user and department creation (2 events)

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