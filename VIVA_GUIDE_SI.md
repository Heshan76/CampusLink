# CampusLink – Viva මාර්ගෝපදේශය (සිංහලෙන්)

> මෙය කට පාඩම් කරන්න නෙවෙයි. එක් එක් කොටස කේතයේ (code) කොහේද කියලා බලලා තේරුම් ගන්න.
> **වැදගත්:** අගයන් (grid 18×6, messages 6, steps 180, nodes 10/20/40) ගත්තේ ඔබේ proposal එකෙන්. Lecturer "හතරැස් grid එකක්" ඉල්ලුවා නම් `campuslink_config.json` හි grid අගය වෙනස් කරන්න (README බලන්න). Assignment PDF එක මට නොලැබුණු නිසා එය ඔබම පරීක්ෂා කරන්න.

---

## 1. මේ project එක මොකක්ද?

Campus එකේ walkway එකක මිනිස්සු අහඹු (random) විදියට ඇවිදිනවා කියලා හිතන්න. දෙන්නෙක් ළඟින් ගියාම phone දෙකෙන් message එකක් මාරු කරගන්න පුළුවන්. Message එකක් destination එකට යවන්න ක්‍රම දෙකක් අපි සසඳනවා:

* **Direct** – message එක තියෙන කෙනා (source) ම destination එක හමුවෙන තුරු තියාගෙන ඉඳලා, හමුවුණාම විතරක් දෙනවා.
* **Epidemic** – message එක තියෙන කෙනා හමුවෙන හැමෝටම copy එකක් දෙනවා. ඒ අයත් ඒක තව අයට පතුරවනවා (රෝගයක් පැතිරෙනවා වගේ).

අපි මනින්නේ:
1. **Delivery percentage** – message කීයෙන් කීයක් ළඟා වුණාද (%)
2. **Average delivery time** – ළඟා වෙන්න simulation steps කීයක් ගියාද
3. **Copies made** – අමතර copies කීයක් හැදුණාද

## 2. Grid එක

Proposal එකේ පරිදි **තීරු 18 × පේළි 6** කින් යුත් පටු campus walkway එකක්. හැම කොටුවක්ම `(x, y)` ලෙස හඳුන්වනවා: `x` = 0 සිට 17, `y` = 0 සිට 5. අගය `campuslink_config.json` එකේ තියෙනවා, code එක වෙනස් නොකර මාරු කරන්න පුළුවන් (උදා: lecturer හතරැස් grid එකක් ඉල්ලුවොත් 16×16).

## 3. Node movement (`movement.py`)

* හැම node එකටම අනන්‍ය ID එකක් (0,1,2…) සහ `(x, y)` පිහිටීමක් තියෙනවා.
* හැම step එකකදීම node එක **නැවතී සිටිනවා හෝ එක කොටුවක්** විතරක් වමට/දකුණට/උඩට/පහළට යනවා (proposal හි "stay or move"). තෝරන්නේ "නැවතී සිටීම" සහ grid ඇතුළේ තියෙන දිශා අතරින් සමාන සම්භාවිතාවෙන්.
* Grid එකෙන් පිටතට යන ගමන් තෝරන්නේ නැහැ – `valid_moves()` function එක grid එක ඇතුළේ තියෙන දිශා විතරක් දෙනවා (කොන් කොටුවක දිශා 2, මායිමක 3, මැදක 4).
* **Wrap-around නැහැ** (එක කෙළවරින් ගියාම අනිත් කෙළවරින් එළියට එන්නේ නැහැ).
* කොටුවක නෝඩ් කිහිපයක් එකට ඉන්න පුළුවන්.

## 4. Contact (හමුවීම) හඳුනාගැනීම (`contact.py`)

**Manhattan distance** භාවිතා කරනවා:

```
distance = |x1 − x2| + |y1 − y2|
```

Distance ≤ 1 නම් (contact radius = 1) ඒ දෙන්නා message මාරු කරගන්න පුළුවන්. ඒ කියන්නේ **එකම කොටුවේ** හෝ **පැත්තකින්/උඩින්/යටින්** ඉන්නවා නම්. **ඇල අතට (diagonal) ඉන්න අයට contact නැහැ** (distance = 2).

උදාහරණ: (3,3)–(3,4) → contact ✔ | (3,3)–(4,4) → contact ✘ | (3,3)–(3,5) → contact ✘.

හැම step එකකම `find_contacts()` හැම node ජෝඩුවක්ම පරීක්ෂා කරනවා. ජෝඩු හැම විටම එකම පිළිවෙළට (a<b, ආරෝහණව) ලැබෙනවා – ඒක නිසා routing හැම වතාවෙම එකම order එකෙන් වැඩ කරනවා (deterministic).

## 5. Messages

Run එකක් පටන් ගන්නකොටම messages 6ක් හදනවා: අනන්‍ය ID, **source**, **destination** (source ට වඩා වෙනස්), සහ creation step = 0.

## 6. Direct routing (`routing.py` → `DirectRouter`)

1. Message එක source ළඟම තියෙනවා.
2. අතරමැද කිසිම node එකකට message එක ලැබෙන්නේ නැහැ.
3. Source සහ destination contact වුණ step එකේදී message එක **හාර දෙනවා (hand-over)** – delivery එක record වෙනවා.
4. Steps 180ක් ඇතුළත හමුනොවුණොත් message එක **undelivered**.
5. **Copy නැහැ.** Hand-over එක කියන්නේ මුල් message එකම දෙන එක; අමතර copy එකක් හදන එක නෙවෙයි. ඒ නිසා Direct හි copies = 0.

## 7. Epidemic routing (`EpidemicRouter`)

* **Holder** = message එක තියෙන node එක. පටන් ගැනීමේදී holder = source පමණයි.
* Holder කෙනෙක් message එක නැති කෙනෙක් හමුවුණාම **copy එකක්** දෙනවා. එකම node එකට එකම message එක දෙවරක් ලැබෙන්නේ නැහැ (`receiver not in holders` පරීක්ෂාව).
* එක step එකකදී message එක ගමන් කරන්නේ **hop එකක්** විතරයි – step එක පටන් ගන්නකොට තිබුණු holders ගේ snapshot එකකින් වැඩ කරනවා. (ඒකෙන් contacts process කරන පිළිවෙළ නිසා copy ගණන වෙනස් වෙන්නේ නැහැ.)
* **Delivery මුලින්ම** බලනවා: destination එක holder කෙනෙක් හමුවුණා නම් ඒ step එකේම delivered, ඒ step එකේ වෙන replication නැහැ.
* Destination එකට ලැබුණාම ඒ message එකේ තවත් පැතිරවීම **නතර** කරනවා (පරීක්ෂණය පාලනය කරගන්න අපි ගත් තීරණයක් – README එකේ සඳහන් කර ඇත).

## 8. "Copy" කියන්නේ මොකක්ද?

Source ළඟ තියෙන **මුල් message එකට අමතරව**, node එකකට message එක **පළමු වතාවට** ලැබෙන හැම අවස්ථාවක්ම copy එකක්. Epidemic හිදී destination එකට ලැබෙන අවසාන copy එකත් ගණනයට ඇතුළත්. Direct = 0.
නැවත නැවත යැවීමේ උත්සාහයන් ගණන් ගන්නේ නැහැ. `transfer_events` කියන වෙනම diagnostic column එකක් තියෙනවා – ඒක copies නෙවෙයි.

## 9. Random seed එක (`scenario.py`)

Computer එකේ "random" කියන්නේ ඇත්තටම සූත්‍රයක් (formula) – පටන් ගන්න අංකය (seed) එකම නම් අහඹු අගයන් ශ්‍රේණියත් එකමයි. ඒ නිසා ප්‍රතිඵල නැවත ලබාගන්න (reproduce) පුළුවන්.

`seed = 42 + (node ගණන × 100) + repetition` – උදා: nodes 20, repetition 1 → **2043**.

**සාධාරණ සැසඳීම:** හැම (node ගණන, repetition) එකකටම *එක* scenario එකක් (ආරම්භක පිහිටීම්, message ජෝඩු, සම්පූර්ණ ගමන් මාර්ගය) seed එකෙන් **routing ට කලින්** හදනවා. Direct සහ Epidemic දෙකම **හරියටම එකම ගමන** නැවත සෙල්ලම් කරනවා. ඒ නිසා වෙනස ඇත්තේ routing ක්‍රමය නිසා පමණයි, වාසනාව නිසා නෙවෙයි. `trace_hash` column එකෙන් මේක ඔප්පු කරන්න පුළුවන් (ජෝඩුවේ දෙන්නාටම එකම අගය).

## 10. ඇයි repetitions 10ක්?

එක run එකක් වාසනාව මත රඳා පවතී (ඉක්මනින් හමුවෙන්නත් පුළුවන්, කවදාවත් නොහමුවෙන්නත් පුළුවන්). වෙනස් seed 10ක් වලින් run කරලා **mean (සාමාන්‍යය)** සහ **standard deviation (විචලනය)** ගත්තාම ප්‍රතිඵලය වඩා විශ්වසනීයයි. Standard deviation ලොකු නම් ප්‍රතිඵල ගොඩක් වෙනස් වෙනවා.

පරීක්ෂණ සැලසුම: 3 node ගණන (10, 20, 40) × 2 ක්‍රම × 10 = **60 runs**.

## 11. Metrics ගණනය

* **Delivery %** = (delivered messages ÷ generated messages) × 100. උදා: 6න් 4ක් → 66.67%.
* **Delivery time** (එක message එකකට) = delivery step − creation step.
* **Average delivery time** = **delivered වූ messages වල** පමණක් සාමාන්‍යය. Undelivered message එකක් "0" ලෙස ගන්නේ **නැහැ** (එහෙම ගත්තොත් ප්‍රතිඵලය බොරු හොඳ වෙනවා). එක message එකක්වත් ළඟා නොවුණොත් අගය හිස් (blank) සහ report එකේ N/A.
* **Copies** = කොටස 8 බලන්න.

## 12. Raw data කොහොමද හැදෙන්නේ?

Simulator එක run වෙන විටම ගොනු සුරකිනවා – අතින් ටයිප් කරන දෙයක් නැහැ.
* `run_logs.csv` – run එකකට පේළි එකක් (official එකේ හරියටම **60**).
* `message_logs.csv` – message එකකට පේළි එකක් (60 × 6 = 360). Run-level අගයන් ස්වාධීනව පරීක්ෂා කරන්න මේක පාවිච්චි වෙනවා.
* `experiment_config.json` – භාවිතා කළ පරාමිතීන්.
* `experiment_manifest.json` – id, වේලාවන්, seeds, validation ප්‍රතිඵලය.

`validation.py` මේ ගොනු නැවත කියවලා හැම අගයක්ම නැවත ගණනය කරනවා, ඒ වගේම හැම run එකක්ම seed එකෙන් **නැවත run කරලා** සුරකින ලද අගයන් සමග සසඳනවා.

**Pilot vs Official:** Pilot ප්‍රතිඵල `outputs/pilot/` ට (වෙනම seeds සමග); official ප්‍රතිඵල `outputs/official/official_<දිනය_වේලාව>/` ට. ඒවා කවදාවත් මිශ්‍ර වෙන්නේ නැහැ.

## 13. MCP server එක මොකටද?

MCP කියන්නේ AI tool එකකට (Antigravity) අපේ project එක පාලනය කරන්න "tools" කිහිපයක් දෙන ක්‍රමයක්. අපේ `CampusLink Control MCP` එකේ tools 6ක් විතරයි: status බැලීම, pilot run, official run, validate, workbook හැදීම, ZIP හැදීම. ඒකට shell access නැහැ, file path ගන්නේ නැහැ.
**Official run එක ආරක්ෂා කර ඇත:** නිවැරදි approval වාක්‍යය "APPROVE OFFICIAL 60-RUN EXPERIMENT", tests pass වී තිබීම, config validate වී තිබීම, කලින් official එකක් නොතිබීම – මේ සියල්ල තිබුණොත් පමණයි run වෙන්නේ.
**MCP එක simulator එක නෙවෙයි.** Simulator එක terminal එකෙන් MCP නැතිවත් වැඩ කරනවා.

## 14. Excel charts කොහොමද හැදෙන්නේ? (`reporting.py`)

* `Run_Data` sheet එකට CSV එකේ පේළි 60 ම කෙලින්ම පිටපත් වෙනවා.
* `Summary` sheet එකේ සංඛ්‍යා **Excel formulas** (`AVERAGEIFS`, `COUNTIFS`, `SUMPRODUCT`) – `Run_Data` මත පදනම්ව. ඒ නිසා data වෙනස් වුණොත් සංඛ්‍යාත් වෙනස් වෙනවා.
* Summary එකට යට "Chart data" වගුවක් formulas වලින් Summary එකට සම්බන්ධ කර ඇත; charts 3ක් (Delivery %, Delivery time, Copies) ඒ වගුවෙන් ඇඳෙනවා. X අක්ෂය = node ගණන, Direct/Epidemic වෙනම series.

## 15. Code map (viva එකේදී පෙන්වන්න)

| ගොනුව | මොකද කරන්නේ |
|---|---|
| `config.py` + `campuslink_config.json` | සියලු පරාමිති එක තැනක |
| `movement.py` | node එක එක කොටුවක් ගමන් කිරීම |
| `contact.py` | Manhattan distance, contacts |
| `scenario.py` | seed එකෙන් පිහිටීම්, messages, ගමන් මාර්ගය |
| `routing.py` | DirectRouter, EpidemicRouter |
| `simulator.py` | step-by-step run, metrics |
| `experiment.py` | 60-run matrix, pilot/official |
| `validation.py`, `gates.py` | පරීක්ෂා සහ ආරක්ෂක දොරටු |
| `reporting.py` | Excel workbook |
| `visualizer.py` | Tkinter සජීවී දසුන |
| `control.py`, `mcp_server.py` | MCP tools |

## 16. ඇසිය හැකි ප්‍රශ්න සහ පිළිතුරු

**ප්‍ර: Direct සහ Epidemic අතර ප්‍රධාන වෙනස?**
Direct – source ම destination හමුවෙන තුරු තබාගෙන, copy නැහැ; ඉක්මන් නැහැ, නමුත් සම්පත් අඩුයි. Epidemic – හැමෝටම copy දෙනවා; ළඟා වීම වැඩි සහ ඉක්මන්, නමුත් copies ගොඩක්.

**ප්‍ර: Direct හි copies ඇයි 0?** Hand-over එක මුල් message එකම දීමක්; copy එකක් හදන්නේ නැහැ. අතරමැද කිසිවෙකුට ලැබෙන්නේ නැහැ.

**ප්‍ර: එකම copy එක දෙපාරක් ගණන් ගන්නේ නැත්තේ කොහොමද?** `holders` කියන set එකේ receiver දැනටමත් ඉන්නවා නම් copy කරන්නේ නැහැ; copy කරන්නේ අලුතින් එකතු වෙනකොට විතරයි, එවිට `copies_created` එක +1 කරනවා.

**ප්‍ර: Delivery time එකට undelivered messages ඇතුළත් කරන්නේ නැත්තේ ඇයි?** ඒවාට delivery time කියා දෙයක් නැහැ. 0 ලෙස ගත්තොත් සාමාන්‍යය බොරුවට අඩු වෙනවා. ඒ නිසා delivered ඒවා පමණක් ගන්නවා; එකක්වත් නැත්නම් N/A.

**ප්‍ර: Seed එක fix කරන්නේ ඇයි?** ප්‍රතිඵල නැවත ලබාගන්න (reproducible) සහ Direct/Epidemic සාධාරණව එකම ගමන මත සසඳන්න.

**ප්‍ර: Node එකකට නැවතී සිටින්න පුළුවන්ද?** ඔව් – proposal එකේ "stay or move one cell" කියන නිසා. `move_node()` හි `[(0,0)] + valid_moves(...)` අතරින් random එකක් තෝරනවා; (0,0) කියන්නේ නැවතී සිටීම.

**ප්‍ර: සියලු messages ළඟා වුණාම run එක නතර වෙනවාද?** නැහැ – proposal එකේ පරිදි steps 180 ම run වෙනවා; ළඟා වූ message එක ඉන්පසු forward කරන්නේ නැහැ. (Visualizer එක පමණක් පෙන්වීමේ පහසුවට ඉක්මනින් නවතිනවා; ප්‍රතිඵල වෙනස් වෙන්නේ නැහැ.)

**ප්‍ර: Diagonal contact ඇයි නැත්තේ?** Manhattan distance එකේදී ඇල අතට distance = 2; radius = 1 නිසා ඇතුළත් නැහැ. Radius 2 කළොත් ඇතුළත්.

**ප්‍ර: Grid එකේ ප්‍රමාණය වෙනස් කරන්න ඕන නම්?** `campuslink_config.json` හි `grid_width`/`grid_height` වෙනස් කරලා tests සහ `validate-config` නැවත run කරන්න. Code වෙනස් කරන්න ඕන නැහැ.

**ප්‍ර: ප්‍රතිඵල අතින් හැදුවේ නැති බව කොහොමද ඔප්පු කරන්නේ?** CSV ගොනු simulator එකෙන් සුරකින ලද ඒවා; `validate` command එකෙන් seed එකෙන් නැවත run කරලා සමාන බව පෙන්විය හැක; screenshot වල run ID සහ seed එක CSV එකේ පේළියට ගැලපෙනවා.

**ප්‍ර: Simulation එකේ සීමාවන්?** සරල random walk, සැබෑ campus සිතියමක් නෙවෙයි; message මාරුව ක්ෂණික සහ දෝෂ රහිත; buffer/expiry නැහැ; repetitions 10 යි; Epidemic delivery පසු පැතිරවීම නතර කරන නිසා copies අඩු වෙනවා.

## 17. Viva demo පිළිවෙළ

1. `campuslink test` – tests සමත් වෙන බව පෙන්වන්න.
2. `campuslink visualize --nodes 20 --method DIRECT --repetition 1` → Start.
3. `campuslink visualize --nodes 20 --method EPIDEMIC --repetition 1` → Start. *(එකම scenario – node චලනය එකමයි.)*
4. Live rerun: `campuslink rerun --nodes 20 --method EPIDEMIC --repetition 1` – official record එක සමඟ MATCH බව පෙන්වන්න.
5. `run_logs.csv` හි `N20_DIRECT_R01` සහ `N20_EPIDEMIC_R01` පේළි, වගේම `message_logs.csv` පෙන්වන්න.
6. Excel හි Summary සහ charts පෙන්වන්න.
