# DEVIL CHATS — Python + Vercel demo

## Deploy to Vercel
1. Upload/extract this folder into a GitHub repository.
2. Import the repository into Vercel.
3. In Vercel Project Settings → Environment Variables, add:
   - `ROOM_SECRET` = a long random secret (do not commit it to GitHub).
4. Deploy.

UI update: blue/red 3D-style glass design and a system banner when the current user joins. Reliable cross-user join/leave presence requires a shared realtime database/service.

Files:
- `api/index.py`: Python serverless API
- `public/index.html`: website UI and browser code
- `vercel.json`: Vercel routes/build configuration
- `requirements.txt`: dependencies (uses Python standard library)

## Important limitations
This is a demo, not production-grade private messaging. Vercel serverless functions are stateless/ephemeral: this code's in-memory room/message store may not be shared across function invocations or instances, so messages may fail to sync consistently. For a real deployed chat, use a persistent/shared store (e.g. Vercel Postgres/Redis/KV or another database) and a realtime service such as Ably/Pusher/Supabase Realtime. Add rate limiting, abuse controls, and secure room authentication.

The shared passphrase alone identifies a room; usernames can differ. Anyone who knows the passphrase can potentially access that room. This demo does not implement end-to-end encryption, so don't send sensitive information. Use HTTPS and a strong `ROOM_SECRET` in deployment.


## Room presence dashboard
The latest UI shows online count, total recorded usernames, each member's online state, and last-seen time. It sends a heartbeat every 5 seconds and marks users offline after about 18 seconds without a heartbeat. **Important:** this demo uses process-local memory. Vercel serverless may route requests to different instances, so member lists, last-seen state, and messages are not guaranteed to sync across devices or persist. For dependable shared presence, configure a persistent shared database/realtime backend such as Supabase.
