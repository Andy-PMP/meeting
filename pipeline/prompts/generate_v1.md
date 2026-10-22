You are writing realistic workplace meeting invites for a dataset. A small classifier will learn to judge whether a meeting should be kept, made shorter, or replaced with an email. A person will read and label every invite by hand, so realism and variety matter more than anything.

Write exactly one invite for each spec below, in the same order, and echo each spec's `spec_id`.

How to use each spec field:
- `gen_hint` is the verdict a thoughtful reader would probably reach:
  - `keep`: the meeting genuinely needs people together live, such as a real decision, a debate, a tricky problem, or collaborative work, with roughly the right people and time.
  - `shorter`: there is a real reason to meet, but it is padded. Too long for its agenda, too many attendees, or a real discussion buried under status updates.
  - `email`: the content is one-way information, status updates, an FYI, or a simple question that a message or email would handle.
- `subtlety` controls how obvious that verdict is. With `obvious`, the signals are clear. With `subtle`, a careful reader can tell, but nothing announces it. With `borderline`, reasonable people could disagree. Never state the verdict, and never write "this could be an email" or similar.
- `meeting_type`, `industry`, `tone`, `length`, `vagueness`: follow them. The word counts in `length` are for the invite text.
- `format` is what the text physically looks like when someone copies it out of their calendar, inbox, or chat app.
- `attendees` and `duration_min`: the invite is sent to that many people for that long. Mention them the way that format naturally would: a time range, an attendee list, "whole team", "all staff", and so on. A short format may leave them implicit.
- `messiness` lists quirks to include, if any. Make them look natural.
- `sender` is the organizer's first name, and `org` is the fictional organization.

Rules:
- Invent every other person, product, and project name. Never use real companies, brands, celebrities, or real people. Keep it workplace-appropriate.
- Make the 5 invites clearly different from one another in topic, wording, and structure. Avoid stock openings like "Hi team, I hope this finds you well" unless the tone calls for them. Real invites rarely sound alike.
- Use plain text only, with "\n" for line breaks. Include no labels, commentary, or explanation, only the invite as a recipient would see it.

Specs:
{{SPECS}}
