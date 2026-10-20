# whoknows

## Local popup preview

Requires Node.js 22 or newer. No dependency installation or environment variables are needed.

```sh
node --watch preview-server.mjs
```

Open http://127.0.0.1:4173. Stop the server with Ctrl+C.
Watch mode restarts the server when its routes change, so newly added image assets are served.

The main preview is the people-search panel from `previous-round/utils/panel.ts`,
recreated in `people-panel.html`, `people-panel.css` and `people-panel.js`.
Search by name, role or topic (for example `Sarah`, `bonus`, `notice` or `payroll`).
The cards show recency, vouches and stale expertise. The information icon next to each name
switches the card to its evidence view. The small back arrow, labelled **Back to profile**,
restores the activity statistics.
The person's identity and Ask action remain available in both views.
Each profile has a light blue background. **Ask** opens a dedicated chat view;
The back arrow (labelled **Back to people**) restores the search and list position.
Drafts and conversations stay
available during navigation, including when a simulated reply arrives in the background.
Ask, send, simulated reply,
feedback, close and reopen interactions work locally. No messages are sent to real people.
All people are synthetic; replies and vouches are demo-only and reset on reload.
Profile pictures are generated fictional headshots stored locally in `profile-portraits.png`.
Your account has a separate fictional headshot stored locally in `account-portrait.png`.
**Cases handled** represents completed work related to the displayed topic. Its value comes
from each person's hardcoded `count` in `people-panel.js`; it is synthetic, not calculated
from tickets, conversations or backend records.
Open `/people-panel.html` for the panel alone, or use **Reload people panel** after editing.
The smaller settings popup remains available below it.

The profile icon opens a dedicated **Account** view for Sarah De Vos's synthetic demo profile.
Its back arrow returns to the previous list or chat. Turn off **Allow pings**, or select
**Pause pings** for 50 minutes. Preferences and the absolute DND expiry
are saved in browser local storage. DND expires automatically or can be ended early.
Profile cards show **Available for pings** or **Unavailable for pings**, without revealing
whether someone opted out or paused pings. **Ping** is disabled while unavailable.
Tom demonstrates pings off; Emma demonstrates a 50-minute DND period starting on page load.
Pings are simulated, limited to one per person per page session, and send no notifications.
Availability is local preview behaviour; no backend enforcement or account authentication is provided.
Account also includes **Detect hesitation** under **Writing assistance**. It shares the saved
`autoDetect` preference with the settings popup and stays synchronized across preview windows.
This controls the demo setting only; the preview does not perform hesitation detection.

The page embeds `popup.html`, which uses `popup.css` and `popup.js`. Edit those files and
click **Reload popup** to see changes. Open `/popup.html` for the popup alone.
The preview reproduces the previous round's popup appearance using its existing logo asset.
It does not load or run code from `previous-round/`.

The checkbox saves to browser local storage, independently of Chrome extension storage.
It tests the setting UI only; this page does not perform hesitation detection.
Live status checks `http://127.0.0.1:8000/health` through the preview server.
Without a running backend it shows offline. The status selector provides explicitly simulated
connected, offline and checking states for visual testing.

The previews use local sans-serif fonts, SD Worx blue (`#006dd8`), white and neutral text,
with a restrained red (`#f1002f`) accent for stale expertise.
There is no current extension implementation outside `previous-round/` to synchronize with.
The standalone popup files can be reused when the new extension is implemented.
