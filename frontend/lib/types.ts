export interface Suggestion {
  id: string;
  topic_id: string;
  trigger: string;
  action: string;
  message: string;
  created_at: string;
  title?: string;
  seen?: boolean;
}
