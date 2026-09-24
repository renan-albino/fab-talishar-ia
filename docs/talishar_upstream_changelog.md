# 📜 Talishar Upstream Changelog & Version Tracking

Este documento registra o histórico de sincronização com os repositórios oficiais do Talishar (Backend e Frontend).
Ele serve como referência para os agentes de IA entenderem exatamente quais mudanças foram introduzidas upstream, quais commits estão ativos e o que precisa de atenção técnica.

---

## 📌 Versões Atualmente Rastreadas

| Repositório | Repositório Remoto | Commit SHA Atual | Data do Commit | Status Local |
| :--- | :--- | :--- | :--- | :--- |
| **Talishar (Backend)** | `https://github.com/Talishar/Talishar.git` | `fb56266f3` (`fb56266f3d9574e28939429240c26da473682efe`) | 2026-09-24 | ✅ Sincronizado + Patches Aplicados |
| **Talishar-FE (Frontend)** | `https://github.com/Talishar/Talishar-FE.git` | `13afdb7b3` (`13afdb7b3ac1214f9c8c13562ebb6192816deaf1`) | 2026-09-24 | ✅ Sincronizado + Patches Aplicados |

---

## 🤖 Guia para Agentes de IA

Quando o Talishar oficial atualizar:
1. **Patches de IA**: Sempre verifique se os arquivos em `setup_templates/` continuam compatíveis com as versões upstream.
2. **Novas Mecânicas/Cartas**: Se houver novidades em `CardDictionaries/`, `extract_card_db.py` é executado automaticamente para atualizar `data/fab_cards_db.json`.
3. **Frontend Vite**: Se novas páginas ou componentes forem adicionados upstream (ex: `AdRailLayout`), garanta que existam mocks adequados em `setup_templates/frontend/bannerUnit/` para compilação offline.

---

## 🕒 Histórico de Sincronizações

### 🔄 Sincronização em 2026-09-24 18:58:46

#### Talishar Backend
- **Transição de Versão**: `6f6eaf26b` (2026-08-28) ➔ `fb56266f3` (2026-09-24)
- **Novos commits incorporados**: 658
- **Ações automáticas executadas**: Código upstream atualizado via fast-forward, Templates customizados reaplicados, Banco fab_cards_db.json reindexado

<details>
<summary><b>Clique para ver a lista de commits incorporados</b></summary>

* `fb56266f3` (2026-09-24 por **PvtVoid**) — Add opt log icon
* `1992fcd59` (2026-09-24 por **PvtVoid**) — Update IARCards.php
* `f9e75a7b1` (2026-09-24 por **PvtVoid**) — Fix replays not showing your arsenal on hover
* `657e2c2f8` (2026-09-24 por **PvtVoid**) — More tiny php performance improvements
* `f42ea1007` (2026-09-24 por **PvtVoid**) — More php performance improvements
* `790cb7a79` (2026-09-24 por **PvtVoid**) — Improve autopitch performance
* `d34d97c71` (2026-09-24 por **PvtVoid**) — php performance improvements
* `a01b38d23` (2026-09-24 por **PvtVoid**) — PHP performance improvements
* `3ce31de6c` (2026-09-24 por **PvtVoid**) — Puzzle + snapshot feature
* `bb87d9657` (2026-09-24 por **PvtVoid**) — Prompt Update
* `e1b0f85e8` (2026-09-24 por **PvtVoid**) — Update IARShared.php
* `54ecb358f` (2026-09-23 por **PvtVoid**) — Revert "Fix for real shadow resist cards being howing a prompt when not taking damage"
* `0cd472224` (2026-09-23 por **PvtVoid**) — Fix for real shadow resist cards being howing a prompt when not taking damage
* `caecae1d5` (2026-09-23 por **PvtVoid**) — Revert "Fix shadow resist cards being howing a prompt when not taking damage"
* `ba8f4155c` (2026-09-23 por **PvtVoid**) — Fix shadow resist cards being howing a prompt when not taking damage
* `afdcdb0f2` (2026-09-23 por **PvtVoid**) — Puzzle updates
* `985369c92` (2026-09-23 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `52be1b492` (2026-09-23 por **Paul Gibby**) — turn on blood debt when levia redeemed is sleeping
* `ac5aaba48` (2026-09-23 por **PvtVoid**) — Add images to prompt
* `04086f520` (2026-09-23 por **PvtVoid**) — Add puzzle tab to mod page
* `30a31acf7` (2026-09-23 por **Paul Gibby**) — ensure the unique rule isn't a may
* `94f7d11e3` (2026-09-23 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `9d523151d` (2026-09-23 por **Paul Gibby**) — fix searching for runechants under amnesia
* `830d05d65` (2026-09-23 por **PvtVoid**) — Don't ask Vynnset prompt if the user is at 1 health
* `6eed69d7f` (2026-09-23 por **PvtVoid**) — Harvest puzzle to try to create daily puzzles
* `4706fd07b` (2026-09-23 por **PvtVoid**) — Review PromptLogs and update logic
* `c2361aaab` (2026-09-23 por **PvtVoid**) — Add default choices options ot Soul Harvest
* `c6c797457` (2026-09-23 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `51ed3f9de` (2026-09-23 por **PvtVoid**) — Only add graveyard if there is an arsenal to remove
* `e91714c71` (2026-09-22 por **Paul Gibby**) — Merge pull request #1419 from Talishar/redo-horror
* `5cd3038b8` (2026-09-22 por **Paul Gibby**) — Merge branch 'main' into redo-horror
* `9ffbeeab5` (2026-09-22 por **Paul Gibby**) — more efficient shadowrealm horror fix
* `42d5cde20` (2026-09-22 por **Paul Gibby**) — rework shadowrealm horror
* `841b077de` (2026-09-22 por **PvtVoid**) — Add a PromptStats to mod page for future analyzes
* `d3e0ba553` (2026-09-22 por **PvtVoid**) — Add auto-pitch with 1 card available + make it a opt out setting if people prefer
* `5d142349f` (2026-09-22 por **PvtVoid**) — Add Vynnset "always pay life" gem toggle option
* `4583344d6` (2026-09-22 por **PvtVoid**) — Skip Katsu popUp if he doesn't have 0 cost cards in hand
* `2b3d9879f` (2026-09-22 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `635559c17` (2026-09-22 por **Paul Gibby**) — fix mark of the funnel web
* `bb42be7e9` (2026-09-22 por **PvtVoid**) — Fix missing bans
* `305e2088c` (2026-09-22 por **PvtVoid**) — Update LinkDeckbuilderAPI.php
* `4e16b704a` (2026-09-22 por **PvtVoid**) — Fix Amulet of Ice ban missing pitch value
* `bd8aa17fa` (2026-09-22 por **PvtVoid**) — Fix fact_finding_mission cardID
* `49ed2efad` (2026-09-22 por **PvtVoid**) — golden_skull_red doesn't exist
* `271e0c46c` (2026-09-22 por **PvtVoid**) — Fix issue with apostrophes in the ban list. People could join with Krakens CC for example
* `05d464958` (2026-09-22 por **PvtVoid**) — Make Korshem not manual
* `5cc1bbe64` (2026-09-22 por **Paul Gibby**) — begin redoing shadowrealm horror
* `7e8ecdcea` (2026-09-22 por **Paul Gibby**) — re-add contracts completed
* `b55723012` (2026-09-22 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `581f7f25f` (2026-09-22 por **Paul Gibby**) — disable contract tracking for now
* `7d9c293b6` (2026-09-22 por **PvtVoid**) — Update StatFunctions.php
* `c8731afea` (2026-09-22 por **PvtVoid**) — Contract Completed Stats
* `3147616c2` (2026-09-22 por **PvtVoid**) — Refactor Talisman of Featherfoot trigger
* `030166343` (2026-09-22 por **PvtVoid**) — Rework Escalate Bloodshed as triggers
* `42eaef795` (2026-09-22 por **PvtVoid**) — Fix tokens going on top of deck not ceasing to exists
* `9086dfb38` (2026-09-21 por **Paul Gibby**) — refactor deadwood rumbler
* `7b619fcca` (2026-09-21 por **Paul Gibby**) — fix beaming bravado with goldfin harpoon
* `1f1572a1b` (2026-09-21 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `b2590046e` (2026-09-21 por **Paul Gibby**) — fix pulsewave harpoon interaction with diabolic offering
* `203218302` (2026-09-21 por **PvtVoid**) — Revert "Stop Arcane hit effects when game is over"
* `e860933d3` (2026-09-21 por **PvtVoid**) — Stop Arcane hit effects when game is over
* `bfd1e86eb` (2026-09-21 por **PvtVoid**) — Fix cachedPreBlockValue being overwritten for the attacking player
* `bf601be15` (2026-09-20 por **Paul Gibby**) — refactor bramble spark
* `76089b624` (2026-09-20 por **Paul Gibby**) — make restless templar trigger first
* `3a8eb1485` (2026-09-20 por **Paul Gibby**) — fix peak power with kayo
* `6fd284680` (2026-09-20 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `bca0c2bd5` (2026-09-20 por **Paul Gibby**) — refactor art of the dragon claw
* `01d353604` (2026-09-20 por **PvtVoid**) — More alt arts
* `28ce884df` (2026-09-20 por **PvtVoid**) — Add NoFirst option to stats so people can include turn 0 if they want
* `f0edf9610` (2026-09-20 por **PvtVoid**) — Refactor ApiBootstrap and MetafyQueries
* `88241901d` (2026-09-20 por **PvtVoid**) — Add ApplyBasePowerSetEffect so card that change base power at only hardcoded once
* `28101647f` (2026-09-20 por **PvtVoid**) — Reuse parsed cache fields
* `5d6b65985` (2026-09-19 por **Paul Gibby**) — update indicator for go again to work with hypothermia (and refactor razor reflex)
* `f25b59e59` (2026-09-19 por **Paul Gibby**) — disable baalghor while he's sleeping
* `6a4f4a0a6` (2026-09-19 por **Paul Gibby**) — fix checking for whether the ally target is still there when dealing damage
* `f28605235` (2026-09-19 por **Paul Gibby**) — fix headstrong stampede and kayo
* `8a301b9d8` (2026-09-19 por **Paul Gibby**) — fix meet madness roll
* `57aebcf00` (2026-09-18 por **Paul Gibby**) — add gem to hex gauntlet
* `70b506df8` (2026-09-18 por **Paul Gibby**) — update Deal2OrDiscard to be more obvious
* `71aad7820` (2026-09-18 por **PvtVoid**) — Fix cloacked equipments showing in pre-game
* `11c24e41b` (2026-09-18 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `e02db35e1` (2026-09-18 por **Paul Gibby**) — fix art of the dragon scale destroying equipment
* `e3ba0cbaa` (2026-09-18 por **PvtVoid**) — Refactor RecordReplayStep
* `54240b552` (2026-09-18 por **PvtVoid**) — Refactor WTR WeaponAttackTargetCards
* `d86924916` (2026-09-18 por **PvtVoid**) — Refactor conditional dominate cards and cards needing ash as target
* `52b5be5dd` (2026-09-18 por **PvtVoid**) — Remove duplicated Character class
* `1d408378e` (2026-09-18 por **PvtVoid**) — Refactor GetRelativeMZZone
* `681e25244` (2026-09-18 por **PvtVoid**) — Refactor BuildMyGamestate
* `a94a9edb1` (2026-09-18 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `4caab6133` (2026-09-18 por **Paul Gibby**) — move banish permission effect checking to be after the NAA shortcut
* `d607e7454` (2026-09-18 por **PvtVoid**) — Show equipped arena cards on hero + remove logs
* `2f0c54388` (2026-09-18 por **PvtVoid**) — Match capitalization to other labels
* `34f8917c4` (2026-09-18 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `be959ce55` (2026-09-18 por **Paul Gibby**) — mark blocking equippment in CHOOSEMULTIZONE
* `6c9fe7b75` (2026-09-18 por **PvtVoid**) — PHP performance improvement
* `637b7ca0b` (2026-09-18 por **PvtVoid**) — Darken Shuko when it's buff has been used
* `a5a4b3fb0` (2026-09-18 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `f0770b09b` (2026-09-18 por **PvtVoid**) — SettingValue functions
* `52ade737f` (2026-09-18 por **Paul Gibby**) — refactor moon wish
* `4dbe4323a` (2026-09-18 por **Paul Gibby**) — add log message for feeding blasmo
* `dadca3faa` (2026-09-18 por **Paul Gibby**) — fix Liars charm to not be subsequent
* `bf4ecf7a5` (2026-09-18 por **Paul Gibby**) — rework quicken to be a proper trigger
* `556aef89d` (2026-09-18 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `115dfa7ff` (2026-09-18 por **Paul Gibby**) — refactor art of the dragon scale with nitro mechanoid
* `95a5fa43a` (2026-09-18 por **PvtVoid**) — Don't WriteLog life lost if you didn't lose life
* `d8d44aac9` (2026-09-18 por **PvtVoid**) — Merge FormatName and FormatCode to 1 function
* `867ca5698` (2026-09-18 por **PvtVoid**) — Fix broken stale composer.lock
* `0aab8e3bf` (2026-09-18 por **PvtVoid**) — Update GetHeroMastery.php
* `b0a9359cf` (2026-09-18 por **PvtVoid**) — Update mastery in-game and lobby + subcards counters hidden
* `7f5dca5a4` (2026-09-17 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `d0a388424` (2026-09-17 por **Paul Gibby**) — fix where stolen allies go when they die
* `40efe1a4a` (2026-09-17 por **PvtVoid**) — Actually fix the stats recording for Shuko
* `2549fe704` (2026-09-17 por **PvtVoid**) — Add back stats for Shuko + fix typo
* `15042e484` (2026-09-17 por **Paul Gibby**) — rework tiger stripe shuko
* `d49e77850` (2026-09-17 por **Paul Gibby**) — more general fix for star struck
* `630976c31` (2026-09-17 por **Paul Gibby**) — fix star struck interaction with reality refractor
* `b4ab8f947` (2026-09-17 por **Paul Gibby**) — mark shadowrealm strength blues setid
* `db70f4815` (2026-09-17 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `61832b445` (2026-09-17 por **Paul Gibby**) — fix minerva themis
* `82a50a5b5` (2026-09-17 por **PvtVoid**) — Fix php error log
* `3c0656a81` (2026-09-17 por **PvtVoid**) — Update SubmitSideboard.php
* `97bd12054` (2026-09-17 por **Paul Gibby**) — mark IAR cards as legal
* `c56ff32c8` (2026-09-17 por **PvtVoid**) — Manual surge creation for Valda
* `a5f0fe421` (2026-09-17 por **PvtVoid**) — Hide deck tab on pre-selection
* `205fbf94e` (2026-09-17 por **PvtVoid**) — Update GetLobbyRefresh.php
* `d3d3b913a` (2026-09-17 por **PvtVoid**) — Dont update the arena cards with matchup button after locking it in
* `bab529fe0` (2026-09-17 por **PvtVoid**) — Update banned cards
* `86a209719` (2026-09-17 por **PvtVoid**) — New pre-game procedure
* `17bb2d8e1` (2026-09-16 por **Paul Gibby**) — fix cintari saber interaction with mirage
* `9c89914b3` (2026-09-16 por **Paul Gibby**) — fix IsWeaponAttack
* `b40176acc` (2026-09-16 por **Paul Gibby**) — explicitly set cleave the heavens effect source
* `1e9412aa2` (2026-09-16 por **Paul Gibby**) — redo glisten
* `ce312b9ea` (2026-09-16 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `fd8d356b7` (2026-09-16 por **Paul Gibby**) — refactor some evo cards to be attack triggers
* `64a678965` (2026-09-16 por **PvtVoid**) — ShowLayerGoAgain setting
* `90b12d759` (2026-09-16 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `37643372e` (2026-09-16 por **Paul Gibby**) — update repentance to have a gem
* `e5f491ab6` (2026-09-16 por **PvtVoid**) — Show go again on layer only on attacks
* `888e06d7e` (2026-09-16 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `2545e9504` (2026-09-16 por **PvtVoid**) — Fix HasBloodDebt flashing when under the effect of Levia Redeemed based on currentPlayer
* `f2bc49263` (2026-09-16 por **Paul Gibby**) — fix context on cleave
* `d33b767cc` (2026-09-16 por **Paul Gibby**) — clean up DRE to track banisher correctly
* `43d05a5a5` (2026-09-16 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `d53dfd3fb` (2026-09-16 por **Paul Gibby**) — allow quickdodge flexors under corrupt and conquer
* `b9f584b11` (2026-09-16 por **PvtVoid**) — minor php performance improvements
* `6eccc9628` (2026-09-16 por **PvtVoid**) — reapply with frontend
* `c268d4038` (2026-09-16 por **PvtVoid**) — Try to force refresh
* `c4fcad41e` (2026-09-16 por **PvtVoid**) — Revert "Add SettingsPieces to prevent error on settings during transfer"
* `363112673` (2026-09-16 por **PvtVoid**) — Add SettingsPieces to prevent error on settings during transfer
* `0ab0ed838` (2026-09-16 por **PvtVoid**) — Show go again on layer
* `310dfb756` (2026-09-16 por **PvtVoid**) — Add StripCardIDSuffix function
* `ad3cb7539` (2026-09-16 por **PvtVoid**) — Remove unused global variables
* `4545bc20c` (2026-09-15 por **PvtVoid**) — More performance improvements in BE
* `eb2e9b99a` (2026-09-15 por **PvtVoid**) — Improve altArt path performances
* `a8db8092c` (2026-09-15 por **PvtVoid**) — More loops performance improvements
* `ed4fa8688` (2026-09-15 por **PvtVoid**) — Another batch of moving functions out of loop or call them once instead of multiple times
* `4ebda11b1` (2026-09-15 por **Paul Gibby**) — fix potential errors in ShadowResist
* `9ae137c55` (2026-09-15 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `0ec940385` (2026-09-15 por **Paul Gibby**) — database update with error fixes
* `5372234cf` (2026-09-15 por **PvtVoid**) — More php improvements and functions out of loops
* `b5cf9df05` (2026-09-15 por **PvtVoid**) — Add Boltyn logic to the bots
* `ccb17c1d7` (2026-09-15 por **Paul Gibby**) — refactor soul harvest
* `61a55546e` (2026-09-15 por **Paul Gibby**) — fix meet madness to work with contracts
* `504f53987` (2026-09-15 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `c1bc430b8` (2026-09-15 por **Paul Gibby**) — really ddisable rally the shadow horde on past chain links
* `69021961b` (2026-09-15 por **PvtVoid**) — Move more stuff from loops for php performance improvements
* `96fb44c3d` (2026-09-15 por **PvtVoid**) — Revert "Make replay links more visually attractive"
* `b7e5e5c3d` (2026-09-15 por **PvtVoid**) — Make replay links more visually attractive
* `f98a1b4a1` (2026-09-15 por **PvtVoid**) — Make settings work across devices
* `7629741ce` (2026-09-15 por **PvtVoid**) — Allow users to turn on/off all gates/auras gems at once
* `1c948bf6c` (2026-09-15 por **PvtVoid**) — More PHP performance improvements
* `cd222aa5a` (2026-09-15 por **PvtVoid**) — Fix Headbanging
* `a5f1679e4` (2026-09-14 por **Paul Gibby**) — fix solforge gauntlet
* `fcb8740db` (2026-09-14 por **PvtVoid**) — Merge pull request #1417 from BennyTheMemer/log-hero-transforms
* `4b808fb40` (2026-09-14 por **PvtVoid**) — Php performance improvements
* `cf6e82d63` (2026-09-14 por **Bernardo Alves**) — log hero transforms in the card turn log
* `2f65648b8` (2026-09-14 por **Paul Gibby**) — disable past chain link activation for rally the shadow horde
* `9f458d17f` (2026-09-14 por **Paul Gibby**) — refactor breakwater undertow
* `7be32285c` (2026-09-14 por **Paul Gibby**) — fix diabolic offering
* `aea806d68` (2026-09-14 por **Paul Gibby**) — fix some more contract cards
* `76ecd70eb` (2026-09-14 por **Paul Gibby**) — add teammate to the Red Line
* `381f1c1ad` (2026-09-14 por **Paul Gibby**) — fix go again on midas touch played at instant speed
* `dc9d9e0f3` (2026-09-14 por **Paul Gibby**) — fix excessive bloodloss effect controller
* `e4b4280b7` (2026-09-14 por **Paul Gibby**) — fix viserai and amnesia
* `747ab65b8` (2026-09-14 por **PvtVoid**) — Fix turn 0 stats
* `75eceb237` (2026-09-14 por **PvtVoid**) — Update IARCards.php
* `936fad4a0` (2026-09-14 por **PvtVoid**) — Add module for paying for d.react (Ataya) for bot
* `ceb7e30c1` (2026-09-14 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `a17d5d38c` (2026-09-14 por **PvtVoid**) — Revert "Fix Tip the Barkeep always going to the bottom of the deck"
* `1c2e142e2` (2026-09-13 por **Paul Gibby**) — fix wind slicer
* `69943441f` (2026-09-13 por **Paul Gibby**) — give levia a new class state to track 6 power cards put into her banish
* `779e8a655` (2026-09-13 por **Paul Gibby**) — fix hiss red
* `6b90ce5d2` (2026-09-13 por **Paul Gibby**) — fix beckoning mistblade
* `833438d63` (2026-09-13 por **Paul Gibby**) — fix leave no witnesses banisher
* `30bdcc458` (2026-09-13 por **Paul Gibby**) — fix hit the gas with non-red hypepr drivers
* `67c804b92` (2026-09-13 por **Paul Gibby**) — fix contact banisher tracking
* `d5630d506` (2026-09-13 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `7cb584d95` (2026-09-13 por **Paul Gibby**) — fix interaction between red lure harpoon and levia's new cards
* `6a94b0d61` (2026-09-14 por **PvtVoid**) — Auto pass pay popUp (e.g. Grains of Bloodspill) if the user has no floating resources and no cards in hand
* `793963827` (2026-09-14 por **PvtVoid**) — Revert "An untapped Hook skips the destroy check entirely. Hard to reach today, but future proof"
* `4afa9eb9b` (2026-09-14 por **PvtVoid**) — An untapped Hook skips the destroy check entirely. Hard to reach today, but future proof
* `d23a67a9f` (2026-09-14 por **PvtVoid**) — Fix Throw Caution to the Wind giving negative prevention if revealing a goldfin harpoon
* `2cde32dbd` (2026-09-14 por **PvtVoid**) — Fix Chart the High Seas comparing an imploded string to an it. php warning
* `54975398f` (2026-09-14 por **PvtVoid**) — Move Jolly Bludger elseif ($from == "COMBATCHAINATTACKS") early. It was unreachable
* `3b05a31ff` (2026-09-14 por **PvtVoid**) — Make Cloud City Steamboat ability type works like Cogwerx Zeppelin and others like that
* `22edc9d4c` (2026-09-14 por **PvtVoid**) — Fix Tip the Barkeep always going to the bottom of the deck
* `cc38727c6` (2026-09-14 por **PvtVoid**) — Fix Money or Your Life if the opponent has 1 gold and you are a thief.
* `75dacaf83` (2026-09-13 por **Paul Gibby**) — fix permanent interment blue power
* `49b596a09` (2026-09-13 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `a3b3bfb63` (2026-09-13 por **Paul Gibby**) — fix meld cards interaction withh warmongers
* `bb3b7916a` (2026-09-13 por **PvtVoid**) — Add a "always wager" gem to Olympia
* `262de8753` (2026-09-13 por **PvtVoid**) — Put a empty deck guard on Scrub the Deck
* `7fb228a37` (2026-09-13 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `650b9e65a` (2026-09-13 por **Paul Gibby**) — fix wind cutter finding non-shuriken items
* `450f31011` (2026-09-13 por **PvtVoid**) — Add Manual Valiant Dynamo setting
* `87d1b47df` (2026-09-13 por **PvtVoid**) — Fix rematch in single player not working
* `c41518918` (2026-09-13 por **PvtVoid**) — Update IraCC.txt
* `7004cae18` (2026-09-13 por **PvtVoid**) — Properly skip rust counters against AI
* `475aed1ce` (2026-09-13 por **Paul Gibby**) — fix violent gusto interactions with sinchants
* `ae229a5b8` (2026-09-13 por **Paul Gibby**) — make grasp of the darknight not contingent on the opt
* `3c42ffaab` (2026-09-13 por **Paul Gibby**) — fix rake over the coals with shurikens
* `d264a74e9` (2026-09-13 por **Paul Gibby**) — remove debug line
* `11dbda17e` (2026-09-13 por **Paul Gibby**) — refactor prismatic leyline
* `6b9afa2a5` (2026-09-13 por **Paul Gibby**) — make spreading flames work with attacking items
* `7ebabb4b9` (2026-09-13 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `f740cde82` (2026-09-13 por **Paul Gibby**) — fix exposed to the elements
* `e5ad3717a` (2026-09-13 por **PvtVoid**) — Paris alt arts
* `ad7faebe1` (2026-09-13 por **PvtVoid**) — Hoarding of Denial counts the wrong cards
* `75d0edc25` (2026-09-13 por **PvtVoid**) — Daily Grind trigger once if there's two copies
* `3135113b3` (2026-09-13 por **PvtVoid**) — Fix Break Stature to work in current turn too
* `eac8fb8de` (2026-09-13 por **PvtVoid**) — Update Stack.php
* `67b0a449c` (2026-09-13 por **PvtVoid**) — Give sunkwater equipment +1 until the end of turn instead of only on the chainlink
* `f7a149d1e` (2026-09-13 por **PvtVoid**) — Add current turn to Annexation of all things in case of go again
* `3fd75720e` (2026-09-13 por **PvtVoid**) — Fix cards destroying auras not being able to target auras on the stack
* `d80f8f669` (2026-09-13 por **PvtVoid**) — Add missing player variable for Crash and Bash
* `cd4e143ba` (2026-09-13 por **PvtVoid**) — Fix Restless drawing if you have an empty hand
* `e5363e0a9` (2026-09-13 por **PvtVoid**) — Update IARCards.php
* `f71f01301` (2026-09-13 por **PvtVoid**) — Fix Head Banging being able to trigger twice a turn
* `e0522bd84` (2026-09-13 por **PvtVoid**) — Make all 3 marks use the same OriginUniqueID
* `af0a8579c` (2026-09-13 por **PvtVoid**) — Fix missing return
* `cca9d2907` (2026-09-13 por **PvtVoid**) — Fix index looking for string instead of int
* `cd0b155a4` (2026-09-13 por **PvtVoid**) — Fix missing parenthesis
* `65156d54d` (2026-09-13 por **PvtVoid**) — Fix suspense destroy trigger not re-checking counters on resolution
* `b0460fbd6` (2026-09-13 por **PvtVoid**) — RemoveSuspense mishandles combat-chain indices
* `b7b03df0a` (2026-09-13 por **PvtVoid**) — Who Blinks First should look at your own aura if you are a guardian hero
* `42e4ce0dc` (2026-09-13 por **PvtVoid**) — Pas proper layer to Not so Tuff
* `7bc45431c` (2026-09-13 por **PvtVoid**) — Fix Hit the Gas can re-flip already face-down Hyper Drivers
* `d3d2747c0` (2026-09-13 por **PvtVoid**) — Fix cards destroying tokens not checking your own
* `cd1afa463` (2026-09-13 por **PvtVoid**) — Fix Liars Charm context
* `a13c15f73` (2026-09-13 por **PvtVoid**) — Fix Unwavering Resolve checking for more than 3 instead of 3 or more
* `7107e6161` (2026-09-13 por **PvtVoid**) — Fix FIght Fair to check uniqueID
* `b051e1091` (2026-09-13 por **PvtVoid**) — Fix Kick the hornets typo
* `ee691d75c` (2026-09-13 por **PvtVoid**) — Fix Turn the Crowd Grateful booing instead of cheering
* `617df0fd5` (2026-09-13 por **PvtVoid**) — Fix Fight Dirty typo
* `e7e845acc` (2026-09-13 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `6bab5797d` (2026-09-13 por **PvtVoid**) — Fix Play () typo and refactor functions used multiple times
* `a3415645d` (2026-09-13 por **PvtVoid**) — Fix Play () typo
* `c953170bc` (2026-09-13 por **PvtVoid**) — Refactor isActivated from Play()
* `8dafdf859` (2026-09-13 por **PvtVoid**) — Fix php error logs
* `258df5e54` (2026-09-12 por **Paul Gibby**) — fix current effect damage prevention amount against heroes with non-physical damage
* `4b840e179` (2026-09-12 por **Paul Gibby**) — disable rally the coast/rearguard on past chain links for now
* `ffc38624e` (2026-09-12 por **Paul Gibby**) — split prevention amount between heroes and allies
* `9eb7ef60b` (2026-09-12 por **Paul Gibby**) — make liars charm discard more obvious
* `e03aebb31` (2026-09-12 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `83fda5b26` (2026-09-12 por **Paul Gibby**) — make enshrine sin not contingent on the opt
* `b5ccc8bc4` (2026-09-12 por **OotTheMonk**) — Return top spectators
* `71fded80a` (2026-09-12 por **Paul Gibby**) — disable limited macro
* `f904eaf26` (2026-09-12 por **Paul Gibby**) — change how physical prevention is tracked
* `893f4d721` (2026-09-12 por **Paul Gibby**) — generated database cleanup
* `5f44abd50` (2026-09-12 por **Paul Gibby**) — allow hooves of the shadow beast to trigger on either players' turn
* `a08dde0ea` (2026-09-12 por **Paul Gibby**) — fix (and refactor) arc ramp
* `51f2d57e7` (2026-09-12 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `8f6657741` (2026-09-12 por **Paul Gibby**) — manual stats for dark arcanite set
* `f92346195` (2026-09-12 por **PvtVoid**) — Fix php error logs
* `6d51d9f24` (2026-09-12 por **PvtVoid**) — Fix Leyline with the new Heave
* `9c51bfc92` (2026-09-12 por **PvtVoid**) — Become the bottle can name itself
* `529d43dd1` (2026-09-12 por **PvtVoid**) — Snarky Prick isn't optional
* `779f8305a` (2026-09-12 por **PvtVoid**) — Fix minor typo on Wind Cutter
* `520748800` (2026-09-12 por **PvtVoid**) — Remove May ability from Recede to Mistform
* `277f8ddaf` (2026-09-12 por **PvtVoid**) — Let Ransack and Raze target a landmark
* `e1b03086c` (2026-09-12 por **PvtVoid**) — Sigil of Silphiadae leave play wasn't passable
* `529936838` (2026-09-12 por **PvtVoid**) — Let you target a hero with Laden with Frost
* `b573a0103` (2026-09-12 por **PvtVoid**) — Make Teklo Trebuchet affecting the next attack even on a different combat chain
* `adfe381b7` (2026-09-12 por **PvtVoid**) — Move Verdant Tide below Ripple Away so Ripple Away can affect it
* `59a86fc0d` (2026-09-12 por **PvtVoid**) — Apply Herald of Victoria -1 to defending cards
* `6a4f7d1f3` (2026-09-12 por **PvtVoid**) — Put mbrio buff even if you activate it before blocking
* `f5c70cf7f` (2026-09-12 por **PvtVoid**) — Don't count facedown cards in banish for effect like Well Grounded, Decompose cards, etc. Now relevant with new Viserai card
* `fdab4abaa` (2026-09-12 por **PvtVoid**) — Fix Phoenix Bannerman not shuffling your deck on fail to find
* `67f9cea85` (2026-09-12 por **PvtVoid**) — Fix php warning on Conquer the Icy Terrain in case 2 of them hits
* `1ef0e3981` (2026-09-12 por **PvtVoid**) — Fix Dyed Silk Sleeves never clearing its effect
* `a272a76f5` (2026-09-12 por **PvtVoid**) — Fix auras using start of turn phase instead of the beginning action phase (Can hold priority)
* `7ba107e16` (2026-09-12 por **PvtVoid**) — Fix Farflight Longbow being usable while tapped
* `902fb1871` (2026-09-12 por **PvtVoid**) — Fix Tempest Dancers only triggering when destroyed (in case it gets banished)
* `f185909ff` (2026-09-12 por **PvtVoid**) — Fix Tentacular Toll cardID for yellow and blue
* `ca49cc5fb` (2026-09-12 por **PvtVoid**) — Fix Burnished Bunkerplate restriction
* `073e5acd9` (2026-09-12 por **PvtVoid**) — Fix Bolt'n Boots arrow restriction
* `e9a36482c` (2026-09-12 por **PvtVoid**) — Remove duplicated gloves_of_azure_waves class
* `2968bef7e` (2026-09-12 por **PvtVoid**) — Fix Gloves of Azure Waves typo
* `d71a47d27` (2026-09-12 por **PvtVoid**) — Fix Spellbane Trap yellow giving +3 instead of +2
* `d56941206` (2026-09-12 por **PvtVoid**) — Clean-up unused code
* `041962651` (2026-09-12 por **PvtVoid**) — Fix Arc Ramp typo
* `b0dd00c18` (2026-09-12 por **PvtVoid**) — Fix Omnious Excavation logs
* `8f088f3b2` (2026-09-12 por **PvtVoid**) — Voltbound Duality red was using a different damage source than yellow/blue
* `b4616c622` (2026-09-12 por **PvtVoid**) — Fix Caress the Reaper and Leech cards triggering on damage dealt to allies. Should be only when damage dealt to a hero
* `9cf020e6e` (2026-09-12 por **PvtVoid**) — Fix Glide Through Starlight not checking if the damage is unpreventable
* `cd3d78b9a` (2026-09-12 por **PvtVoid**) — Add missing check to Arcanic Reproach so it doesn't trigger on self inflicted damage
* `898338ec6` (2026-09-12 por **PvtVoid**) — Add Lightning check to Snap Fingers
* `169bc5c2e` (2026-09-12 por **PvtVoid**) — Fix Flow Through doing nothing when played on the layer step
* `4e11dc69e` (2026-09-12 por **PvtVoid**) — Add destroyedBy to aura being destroyed. Card like Astral Strike count if you destroyed you opponeng lightning flow and should be active instead of checking only your own you destroyed
* `19cee3510` (2026-09-12 por **PvtVoid**) — Fix Fortitude of Anvilheim loop variable being mixed up
* `df269c39b` (2026-09-12 por **PvtVoid**) — Fix Olde Leather counting attacks against allies as attacks against the hero
* `12ae11387` (2026-09-12 por **PvtVoid**) — Under Amnesia you cannot choose nameless cards from Lessons Learned
* `ad34fbb6a` (2026-09-12 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `274c77de1` (2026-09-12 por **PvtVoid**) — Fix Shove off to allow to return cards to hand from previous chain links
* `09b9cb55a` (2026-09-12 por **PvtVoid**) — Fix Twart fatal error on $Weapon->NumPowerCounters() if not blocking a weapon
* `b4e445faf` (2026-09-12 por **PvtVoid**) — Fix Twart fatal error on $Weapon->NumPowerCounters() if not blocking a weapon
* `2d588ed9a` (2026-09-12 por **PvtVoid**) — Fix Shove off to allow to return cards to hand from previous chain links
* `b536d8e0b` (2026-09-12 por **PvtVoid**) — Fix A Moment's Peace not letting the player attacking allies/spectra/etc
* `68a481a8a` (2026-09-12 por **PvtVoid**) — Fix Off Beat not letting your destroy tokens from opponents
* `94886e73d` (2026-09-12 por **PvtVoid**) — Fix Terms of Combat drawing you cards if the effect is active and you aren't attacking with a weapon.
* `22c903a50` (2026-09-12 por **PvtVoid**) — Fix Blunt Retort being a "may" effect and not mandatory
* `b56359288` (2026-09-12 por **PvtVoid**) — Update stats and remove sense weakness from dmg prevented
* `981711a19` (2026-09-12 por **PvtVoid**) — Fix lose health in stats
* `85b805fb4` (2026-09-12 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `d1a36bcef` (2026-09-11 por **Paul Gibby**) — step through realms block fix
* `0231047c0` (2026-09-11 por **Paul Gibby**) — fix devouring doomwake banishing cards into the wrong zone
* `971f6eacc` (2026-09-11 por **Paul Gibby**) — fix promise of power not removing
* `223f9d2f5` (2026-09-11 por **Paul Gibby**) — fix promise of power
* `73b7e6416` (2026-09-11 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `4ef98d370` (2026-09-11 por **PvtVoid**) — Don't close the game if someone is deck organizing
* `cf9de09b3` (2026-09-11 por **Paul Gibby**) — fix default banisher
* `1fefc7d9c` (2026-09-11 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `90c35f81b` (2026-09-11 por **Paul Gibby**) — allow defensive cards to be activated on past chain links
* `6254310e1` (2026-09-11 por **PvtVoid**) — Update BotLogic.php
* `2148d6b0f` (2026-09-11 por **PvtVoid**) — Some bot improvements/changes
* `b5118e1b8` (2026-09-11 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `18f77bb88` (2026-09-11 por **PvtVoid**) — New alt arts
* `1dd6851c0` (2026-09-11 por **PvtVoid**) — Fix combat dummy targeting
* `34b3ea716` (2026-09-11 por **Paul Gibby**) — consuming appetite go again fix
* `e7a51677d` (2026-09-11 por **Paul Gibby**) — remove go again from feasting shadowbeast
* `04395044b` (2026-09-11 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `a194da3a1` (2026-09-11 por **Paul Gibby**) — fix shadowrealm swiftness
* `b8c36cecf` (2026-09-11 por **PvtVoid**) — Rework the single player bots
* `652bd6324` (2026-09-11 por **Paul Gibby**) — clean up blasmo clearing interface
* `6413d5f32` (2026-09-11 por **Paul Gibby**) — remove debug lines
* `39b97a2f1` (2026-09-11 por **Paul Gibby**) — fix blasmo ability refreshing when you make a new blasmo
* `8fdc099dc` (2026-09-11 por **Paul Gibby**) — fix cleave the heavens block value
* `3f2114ba8` (2026-09-11 por **Paul Gibby**) — better fix for modifiedpowervalue
* `a5f5bdaf1` (2026-09-11 por **Paul Gibby**) — fix modified PowerValue with base checks
* `334818634` (2026-09-11 por **Paul Gibby**) — fix ingest the unknown
* `a5e66c977` (2026-09-11 por **PvtVoid**) — Fix Mutual Sacrifice wrong player ID, Apex Buster not re-checking its target on resolution and couple of cards not using ModifiedPowerValue
* `765ff7c05` (2026-09-11 por **Paul Gibby**) — Make devouring doomwake work on past link defending cards
* `d3681565f` (2026-09-11 por **Paul Gibby**) — include omn cards
* `73407869a` (2026-09-11 por **Paul Gibby**) — fix fresh from the forge
* `c501370c4` (2026-09-11 por **Paul Gibby**) — rework exposed to the elements and fix interaction with skullcap
* `1a7e1455a` (2026-09-11 por **PvtVoid**) — Permanent Interment fix
* `118dc08fa` (2026-09-11 por **PvtVoid**) — Dam the Shadowake bug fix
* `c6594cdf0` (2026-09-11 por **PvtVoid**) — Enshrine Sin
* `af15692ca` (2026-09-11 por **PvtVoid**) — Hoodwink, Fresh from the Forge, Wind Slicer and Permanent Interment
* `6dbcf446a` (2026-09-11 por **PvtVoid**) — Abyssal, i'Arathael, Whispers Within, Cogwerx Prong Bot and Favorable Winds
* `e9342844d` (2026-09-11 por **PvtVoid**) — Add Commit to Corruption block value
* `51d383de7` (2026-09-11 por **PvtVoid**) — Rise to the challenge and Rocktop Bellow
* `afc8c2938` (2026-09-11 por **PvtVoid**) — Step Through the Realms, Rally the Shadow Horde and Corpse Cover
* `a36da3564` (2026-09-11 por **PvtVoid**) — Shadowake GloomBlade
* `370002e32` (2026-09-11 por **PvtVoid**) — promise_of_power_yellow
* `1b9bcdff4` (2026-09-11 por **PvtVoid**) — More cards
* `139a0c4a0` (2026-09-11 por **PvtVoid**) — Reverse $amount and $player in GainRessources so it matches the order of other Gain/Lose functions
* `7abe30f86` (2026-09-11 por **PvtVoid**) — Shadow brute cards
* `a95b081e2` (2026-09-11 por **PvtVoid**) — Update docker-compose.yml
* `4cbd8fec9` (2026-09-11 por **PvtVoid**) — rumbling_hunger
* `bd55c7325` (2026-09-11 por **PvtVoid**) — banneret_of_swordsmanship_yellow
* `cb1645ef0` (2026-09-11 por **PvtVoid**) — Database update
* `e6b31c238` (2026-09-11 por **PvtVoid**) — Arcanite equipments
* `a275a0896` (2026-09-10 por **Paul Gibby**) — generated pull and cleanup
* `2bc0f0910` (2026-09-10 por **Paul Gibby**) — disable undo limit in bot games
* `f989dfb4d` (2026-09-10 por **Paul Gibby**) — make baalghor work for their opponent's stolen cards
* `0106532ec` (2026-09-10 por **PvtVoid**) — appalling_bearers display leftover prevention
* `f83f6fcd4` (2026-09-10 por **PvtVoid**) — Display how much is left of prevention on Fallen Herald
* `eb3f1c51f` (2026-09-10 por **Paul Gibby**) — rework diabolic offering
* `8e123d8e2` (2026-09-10 por **Paul Gibby**) — remove debug line
* `39429b0c4` (2026-09-10 por **Paul Gibby**) — refactor courage
* `ecb408ffd` (2026-09-10 por **PvtVoid**) — Add arcane threatened to allies in stats
* `8ce3d5f9a` (2026-09-10 por **PvtVoid**) — Add log and count to forbidden_harvest_yellow
* `ce68296fa` (2026-09-10 por **Paul Gibby**) — make bloodsong gloomblade targeting optional
* `dcaa56dad` (2026-09-10 por **Paul Gibby**) — fix shadow resist talent checking
* `6714230e2` (2026-09-10 por **Paul Gibby**) — remove error log message
* `d9cb56a32` (2026-09-10 por **Paul Gibby**) — add log message
* `d3a27bf62` (2026-09-10 por **Paul Gibby**) — better fix notice
* `27716bdc4` (2026-09-10 por **Paul Gibby**) — fix notice
* `5dd75c4cd` (2026-09-10 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `32dd19172` (2026-09-10 por **Paul Gibby**) — fix fallen herald blood debt
* `0fe0c784c` (2026-09-10 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `6ad61e120` (2026-09-10 por **PvtVoid**) — Couple minor changes
* `5d99baa76` (2026-09-10 por **Paul Gibby**) — shadow resist cards
* `6a5404df3` (2026-09-10 por **Paul Gibby**) — Merge branch 'main' into shadow-resist
* `5522b54fb` (2026-09-10 por **Paul Gibby**) — fix fallen herald talent
* `0f5d77e6f` (2026-09-10 por **Paul Gibby**) — add missing colors, fallen herald, organize armory deck cards
* `16ad96e05` (2026-09-10 por **PvtVoid**) — Fix php error logs
* `86330f9d2` (2026-09-10 por **PvtVoid**) — Fix deck organizer bug
* `9b0bd0935` (2026-09-10 por **PvtVoid**) — Remove ReissueUndoRequestWithReason
* `ee4ce3449` (2026-09-10 por **PvtVoid**) — Add manual mode options
* `8391ea7c6` (2026-09-09 por **Paul Gibby**) — Dam the Shadowake
* `fb57d4954` (2026-09-09 por **Paul Gibby**) — first attempt at making shadow resist work
* `ec10ccc84` (2026-09-09 por **Paul Gibby**) — fallen herald prototype
* `37ea8ac09` (2026-09-09 por **Paul Gibby**) — fix meet madness and open the gate
* `333155ee3` (2026-09-09 por **Paul Gibby**) — fix viserai and contracts
* `b3eb67db2` (2026-09-09 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `6a6732916` (2026-09-09 por **Paul Gibby**) — return if no ally is created
* `3fc860d2d` (2026-09-09 por **PvtVoid**) — Add AuraDefaultActiveState
* `b7d5db890` (2026-09-09 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `1474ec891` (2026-09-09 por **Paul Gibby**) — show targeted card in graveyard for invert existence
* `d45c0d93d` (2026-09-09 por **PvtVoid**) — Snapshot card to heave at the start of the endphase
* `058178567` (2026-09-09 por **PvtVoid**) — Disguise Heave as Arsenal
* `b0d416432` (2026-09-09 por **PvtVoid**) — Add gate defautl state
* `a01b38940` (2026-09-09 por **Paul Gibby**) — fix bloodfrenzy gloomblade go again
* `3bb973100` (2026-09-09 por **Paul Gibby**) — refactor murmuring gloomblade
* `3da813ac5` (2026-09-09 por **Paul Gibby**) — fix bloodfrenzy gloomblade pitch value
* `8a8ceb07a` (2026-09-09 por **Paul Gibby**) — fix warning in popup
* `f1073c6e3` (2026-09-09 por **Paul Gibby**) — fix warning
* `62fc73119` (2026-09-09 por **Paul Gibby**) — make corrosive space dust interact correctly with chromatic refinement
* `19a6d71e1` (2026-09-09 por **Paul Gibby**) — add malice precon
* `6e585d3fb` (2026-09-08 por **Paul Gibby**) — adding comment
* `39d91cdcc` (2026-09-08 por **Paul Gibby**) — fix rites of nightfall class
* `384cc89bf` (2026-09-08 por **Paul Gibby**) — AMA cards
* `48bbe90ce` (2026-09-08 por **Paul Gibby**) — fix hala with new base card update
* `dcbaf7b6f` (2026-09-08 por **Paul Gibby**) — update trade in to be cleaner
* `323211680` (2026-09-08 por **Paul Gibby**) — attempt to update card objects to better support base cards
* `de885221f` (2026-09-08 por **Paul Gibby**) — best fix for BanishFromHand
* `3bf89006b` (2026-09-08 por **Paul Gibby**) — fix figment of hope talent
* `5462dc414` (2026-09-08 por **PvtVoid**) — Remove more unused files and code
* `dbd8cf95e` (2026-09-08 por **Paul Gibby**) — better fix for shadowpede
* `c0e67a66e` (2026-09-08 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `866ea643e` (2026-09-08 por **Paul Gibby**) — fix BanishFromHand interaction with shhadowpede
* `13712814b` (2026-09-08 por **PvtVoid**) — Add equipment being destroy animation when blocking
* `015849aa7` (2026-09-08 por **Paul Gibby**) — update banish from hand to be more obvious
* `e0bd9768f` (2026-09-08 por **Paul Gibby**) — allow war cry of bellona to choose to banish 0 cards
* `cf8822dc9` (2026-09-08 por **PvtVoid**) — GameUID rematch test
* `9b428e0dc` (2026-09-08 por **PvtVoid**) — Make a checkpoint at start of your turn when you revert
* `d964ad270` (2026-09-08 por **PvtVoid**) — Remove unused code
* `f45e5b99a` (2026-09-08 por **Paul Gibby**) — working trade in refactor
* `bc4817dba` (2026-09-08 por **Paul Gibby**) — Revert "trade in refactor"
* `68abab57b` (2026-09-08 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `fd3844143` (2026-09-08 por **Paul Gibby**) — trade in refactor
* `66e3cce6f` (2026-09-08 por **PvtVoid**) — Remove all unused stuff / roguelike / legacy
* `d7b3d6649` (2026-09-08 por **PvtVoid**) — Refactor json_decode and http_response_code
* `acac59f2e` (2026-09-08 por **PvtVoid**) — Update GetLastActiveGame.php
* `bbc048ab6` (2026-09-08 por **PvtVoid**) — Don't wipe out players seat when games is finish and you refresh
* `ed6806ee1` (2026-09-08 por **PvtVoid**) — Update NetworkingLibraries.php
* `497ffbf7e` (2026-09-08 por **PvtVoid**) — Update manual mode to work with things like Snacth|2
* `cda8b9e7f` (2026-09-07 por **PvtVoid**) — Reduce the amount of "dead" call to APIs\GetLobbyRefresh.php
* `48ccfdcf7` (2026-09-07 por **PvtVoid**) — Refactor CombatChainState
* `37dca3bff` (2026-09-07 por **PvtVoid**) — Refactor GetDamagePreventionWarning
* `edbbf1321` (2026-09-07 por **Paul Gibby**) — add missing blood debt
* `1f15dcf9c` (2026-09-07 por **Paul Gibby**) — fix ripple away interaction with sinchants
* `d6d36e75b` (2026-09-07 por **Paul Gibby**) — more robust fix to mark of ushering
* `732679e23` (2026-09-07 por **PvtVoid**) — Fix Mark of Ushering not being affected by Ripple Away
* `bfcfcc25c` (2026-09-07 por **PvtVoid**) — Reapply "Some more cleanup of unused function_exists functions"
* `e4e01714e` (2026-09-07 por **PvtVoid**) — Fix the issue with previous push and php error logs
* `d665d257a` (2026-09-07 por **PvtVoid**) — Revert "Some more cleanup of unused function_exists functions"
* `b2cf2a12a` (2026-09-07 por **PvtVoid**) — Some more cleanup of unused function_exists functions
* `d65453e89` (2026-09-07 por **PvtVoid**) — Clean-up useless function_exists
* `35c620e76` (2026-09-07 por **PvtVoid**) — Remove Bonne Barrier visual effect
* `c61092f7e` (2026-09-07 por **Paul Gibby**) — bloodfrenzy gloomblade pitch value
* `f04717fd0` (2026-09-07 por **PvtVoid**) — Add a new version to replays to work better for future replays
* `27f081069` (2026-09-07 por **PvtVoid**) — Show attacking ally subcards on the combat chain if there are any
* `7ce6d1ca8` (2026-09-07 por **PvtVoid**) — More refactoring
* `19cbbe288` (2026-09-07 por **PvtVoid**) — Add log to Embraforge
* `97947048b` (2026-09-07 por **PvtVoid**) — Fix Glooblade
* `6edb87dbd` (2026-09-06 por **Paul Gibby**) — fix tome of necrosis with no allies
* `910636668` (2026-09-06 por **Paul Gibby**) — fix corrupted corpse dead threads interaction
* `c384477de` (2026-09-06 por **Paul Gibby**) — vis precon gloomblades
* `d50e861ed` (2026-09-06 por **Paul Gibby**) — fix cleave the heavens
* `4d7c85911` (2026-09-06 por **Paul Gibby**) — refactor draconic targeting attack triggers
* `8dc6fa434` (2026-09-06 por **Paul Gibby**) — fix shadowrealm bloodhound
* `297879adc` (2026-09-06 por **Paul Gibby**) — give shadowrealm cards blood debt
* `5982bcd02` (2026-09-06 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `91dbbea3a` (2026-09-06 por **Paul Gibby**) — gem pack cards
* `d46d49569` (2026-09-06 por **PvtVoid**) — Refactor duplicated SetCombatChainState, PayResourcesFromPool and TryPOSTData
* `239b28a38` (2026-09-06 por **PvtVoid**) — Add "attacking" label to your own allies
* `927849758` (2026-09-06 por **PvtVoid**) — I don't think it's needed from hand
* `82d50e871` (2026-09-06 por **PvtVoid**) — Add Gated label
* `ed57a7380` (2026-09-06 por **PvtVoid**) — Fix Geyser going negative for ever
* `2a45988ee` (2026-09-06 por **PvtVoid**) — Update AllAltArtVariations.php
* `0beadb116` (2026-09-06 por **PvtVoid**) — Show subcards in popups
* `6392b698c` (2026-09-06 por **PvtVoid**) — Show binds overlay in the playerInputPopUp
* `b332ae983` (2026-09-06 por **PvtVoid**) — Add border effect to Phoenix form when 3 phoenix are on the chain and active
* `564220aed` (2026-09-06 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `2f01f2f62` (2026-09-06 por **Paul Gibby**) — fix arknight descendancy power
* `8223a8ec6` (2026-09-06 por **PvtVoid**) — Fix SET_ShortcutAttackThreshold not being restarted properly for both players each turns
* `9e2909432` (2026-09-06 por **Paul Gibby**) — fix sonata dystopia off creepers
* `14ef84ba6` (2026-09-06 por **Paul Gibby**) — shadowrealm jabs
* `4519ef940` (2026-09-06 por **Paul Gibby**) — cleave the heavens prototype
* `99be36b49` (2026-09-06 por **Paul Gibby**) — headstrong stampede prototype
* `b690548f1` (2026-09-06 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `b6045bf4e` (2026-09-06 por **Paul Gibby**) — zombie jabs
* `20446393e` (2026-09-06 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `43ebb6dc8` (2026-09-06 por **PvtVoid**) — Fix binds subcards
* `639b6a4c1` (2026-09-06 por **Paul Gibby**) — breach flesh prototype
* `278d99a3d` (2026-09-06 por **Paul Gibby**) — corporeal chasm prototype
* `a2979466f` (2026-09-06 por **Paul Gibby**) — fix mark power modifiers
* `ad299031f` (2026-09-06 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `3e9426a67` (2026-09-06 por **Paul Gibby**) — forbidden harvest and arknight descendancy
* `bc9165aca` (2026-09-06 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `667c01684` (2026-09-06 por **PvtVoid**) — Update IARCards.php
* `1cbca8101` (2026-09-06 por **Paul Gibby**) — marks
* `f1ba9ab2b` (2026-09-06 por **Paul Gibby**) — brute cards
* `54e445921` (2026-09-06 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `11c89fb80` (2026-09-06 por **Paul Gibby**) — blessing of themis should not work on created cards
* `9aef09e4a` (2026-09-06 por **PvtVoid**) — Use CountAttackingTurns to count turn stats per players instead of currentTurn. Should fix the bugs related to having an extra turn
* `d82240259` (2026-09-06 por **PvtVoid**) — Use GeneratedHasFusion for HasFusion
* `ae751aba8` (2026-09-06 por **PvtVoid**) — Remplace the manually coded simple arcane barrier with the GeneratedArcaneBarrierAmount
* `734f531a0` (2026-09-06 por **PvtVoid**) — Refactor gem check to do all zone in GetLayerGemStatus
* `40d61260e` (2026-09-06 por **PvtVoid**) — Fix art_of_the_dragon_fire_red targeting
* `898b3527f` (2026-09-06 por **PvtVoid**) — Fix Red Hot targeting
* `4215b97ee` (2026-09-06 por **PvtVoid**) — Fix php error logs
* `6cf11db82` (2026-09-05 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `ff5bb3626` (2026-09-05 por **Paul Gibby**) — fix star struck and attack queue attacks
* `c1d9a377e` (2026-09-05 por **PvtVoid**) — Minor logs fixes
* `f6b95c4f1` (2026-09-05 por **PvtVoid**) — channel_stormgarden_yellow hasFlowCounters
* `216208539` (2026-09-05 por **PvtVoid**) — Fix preview.talishar issues
* `26417dc20` (2026-09-05 por **PvtVoid**) — Downgrade minerva
* `dd9452615` (2026-09-05 por **Paul Gibby**) — shadowrealm bloodhound prototype
* `084c0f6e0` (2026-09-05 por **Paul Gibby**) — peak power prototype
* `62cbe4f64` (2026-09-05 por **Paul Gibby**) — downshift the hand that pulls the strings
* `aba3076e7` (2026-09-05 por **Paul Gibby**) — restless templar, looter, and tome
* `798e37ad3` (2026-09-04 por **Paul Gibby**) — fix cheaters charm in the layer step
* `4ce9b1d90` (2026-09-04 por **PvtVoid**) — Make the auto pass feature opt-in
* `63238e35c` (2026-09-04 por **Paul Gibby**) — boneseer skullcap
* `e937c3c06` (2026-09-04 por **Paul Gibby**) — better handle dig for souls with x=1 and missing a zombie
* `c1b4775bb` (2026-09-04 por **Paul Gibby**) — fix astral ambience fragment trigger
* `e81b6620c` (2026-09-04 por **Paul Gibby**) — give doomwake blood debt
* `6aef1dc77` (2026-09-04 por **Paul Gibby**) — devouring doomwake prototype
* `a538efc38` (2026-09-04 por **Paul Gibby**) — exorcism and violent gusto
* `a7e5c86bc` (2026-09-04 por **PvtVoid**) — Fix players sometime note being able to click first/second
* `e9e9a3345` (2026-09-04 por **PvtVoid**) — Improve Bound performances passing from O(allies × n) to O(allies + n) check instead
* `fbd82dbfd` (2026-09-04 por **PvtVoid**) — Try to fix undo breaking replays
* `33d6e5a0d` (2026-09-04 por **PvtVoid**) — Only shuffle once
* `79dd41360` (2026-09-04 por **PvtVoid**) — Fix Phoenix Flame being auto selected by the wrong effect
* `968f5e15f` (2026-09-03 por **Paul Gibby**) — restless looter prototype
* `acadd5817` (2026-09-03 por **Paul Gibby**) — tome of necrosis prototype
* `7009ab075` (2026-09-03 por **Paul Gibby**) — 9/3 database pull
* `da52d6e62` (2026-09-03 por **Paul Gibby**) — fix darkest hour alt cost while a shadow attack is active
* `339f256d7` (2026-09-03 por **PvtVoid**) — Option to disable auto-pass
* `a6cb9f9ce` (2026-09-03 por **Paul Gibby**) — violent gusto prototype
* `d5e3ef4b0` (2026-09-03 por **Paul Gibby**) — display bound auras as subcards
* `ef9cddc9b` (2026-09-03 por **Paul Gibby**) — all 3 mark prototypes ready
* `26e4c5cbb` (2026-09-03 por **Paul Gibby**) — Merge pull request #1415 from Talishar/binds-with
* `11c9819f8` (2026-09-03 por **Paul Gibby**) — add comment
* `d29407cee` (2026-09-03 por **Paul Gibby**) — finish prototype of mark of ushering
* `ed67154fe` (2026-09-03 por **Paul Gibby**) — first steps at implementing bound auras
* `dbf7da239` (2026-09-03 por **Paul Gibby**) — properly benched ira
* `9a4843831` (2026-09-03 por **Paul Gibby**) — refactor tome of duplicity
* `08ff093ad` (2026-09-03 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `0bc816024` (2026-09-03 por **Paul Gibby**) — prototype restless templar
* `1c577fd5d` (2026-09-03 por **PvtVoid**) — More alt arts
* `5d3c35658` (2026-09-03 por **PvtVoid**) — New alt arts
* `262cfcc44` (2026-09-03 por **Paul Gibby**) — add a comment to bounding demigon
* `63b17f2d6` (2026-09-03 por **Paul Gibby**) — fix bounding demigon go again
* `96ab8f7c9` (2026-09-03 por **PvtVoid**) — Make the pass button do more (hold to pass priority until end of turn for everything)
* `9688b764a` (2026-09-03 por **PvtVoid**) — Update ELERanger.php
* `827e67d1a` (2026-09-03 por **PvtVoid**) — Put spoilers cards live
* `1f499a648` (2026-09-03 por **PvtVoid**) — zzImageConverter update
* `7c2867b12` (2026-09-03 por **PvtVoid**) — Simplify AND fusions
* `b1a187705` (2026-09-02 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `01d25db65` (2026-09-02 por **Paul Gibby**) — refactor bounding demigon
* `5fa75cae9` (2026-09-02 por **PvtVoid**) — Fix php error logs
* `abea3d040` (2026-09-02 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `a56349335` (2026-09-02 por **Paul Gibby**) — handle case of 2 traverse triggers on the stack
* `a496d7f56` (2026-09-02 por **PvtVoid**) — Make accepting a friend request is atomic leaving "pending" instead of empty
* `9487ef935` (2026-09-02 por **PvtVoid**) — Write a warning before a stale game (5min+ on the live server will close)
* `6d8bcc7f4` (2026-09-02 por **PvtVoid**) — Removed the unused connection from PasswordLogin().
* `d961dcb33` (2026-09-02 por **Paul Gibby**) — add a comment
* `bc873547e` (2026-09-02 por **Paul Gibby**) — make sure exorcism works with kiss of death
* `39de6675a` (2026-09-02 por **Paul Gibby**) — exorcism prototype
* `9c4e87ac9` (2026-09-02 por **Paul Gibby**) — channel stormgarden prototype
* `ee356301d` (2026-09-02 por **Paul Gibby**) — generated pull 9/2
* `e9572ac95` (2026-09-01 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `9be75905c` (2026-09-01 por **Paul Gibby**) — add log message for circlet
* `27c478579` (2026-09-01 por **PvtVoid**) — Move arsenal check up
* `eceded252` (2026-09-01 por **PvtVoid**) — Load zone lazily so we can return early without watching ressources
* `098e37315` (2026-09-01 por **PvtVoid**) — Add more player macros to skip popup (e.g. prizeworn_pathfinders, staunch_response, song of sinew, and other cards that leave you with 1 choice to put back on top of your deck for example
* `b807295fd` (2026-09-01 por **PvtVoid**) — Update list of cards with automatic choice if all options are the same card ID and mandatory effect
* `e275174c2` (2026-09-01 por **Paul Gibby**) — bravery of the blade prototype
* `81fa2c2a3` (2026-09-01 por **Paul Gibby**) — blessing of suraya prototype
* `bf4882196` (2026-09-01 por **Paul Gibby**) — fix astral ambience and end of turn aura untapping
* `2afa87b3e` (2026-09-01 por **Paul Gibby**) — Reach of the Abyss
* `9b2a2c4e3` (2026-09-01 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `6590ab6a5` (2026-09-01 por **Paul Gibby**) — don't count weapons with headbanging chorus
* `edef7d098` (2026-09-01 por **PvtVoid**) — Couple more minor UI changes
* `45727ae63` (2026-09-01 por **PvtVoid**) — Fix couple of logs and minor typo's
* `6f53ef487` (2026-09-01 por **PvtVoid**) — Create IsCardSpecificPitchRestricted and add AoW Phoenix to prevent players from pitching their single Phoenix Flame
* `7c8279037` (2026-09-01 por **PvtVoid**) — Prevent players from pitching their only zombie while paying for Undead Grasp
* `9b34eefcb` (2026-09-01 por **PvtVoid**) — Update IARCards.php
* `b9334aab3` (2026-09-01 por **PvtVoid**) — Auto choose for Dirge if all auras are the same
* `b8ffbfa1d` (2026-09-01 por **PvtVoid**) — Revert "Reimplement link auth key to players account"
* `d25feee04` (2026-08-31 por **Paul Gibby**) — uncomment gesture of goodwill
* `cd35358d5` (2026-08-31 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `750fa0eb4` (2026-08-31 por **Paul Gibby**) — fix oasis respite targeting of past chain links
* `417ce4929` (2026-08-31 por **PvtVoid**) — Allow users to delete replays
* `994f47468` (2026-08-31 por **PvtVoid**) — Match capitalization to the rest of the $labels
* `e84021888` (2026-08-31 por **PvtVoid**) — Update BuildPlayerInputPopup.php
* `67f44726d` (2026-08-31 por **Paul Gibby**) — update usurp handling to use $label
* `61c0bbd24` (2026-08-31 por **Paul Gibby**) — prototype allowing usurps to be re-ordered
* `382613401` (2026-08-31 por **Paul Gibby**) — mark consuming appetite as implemented
* `6c35c4963` (2026-08-31 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `415544fc4` (2026-08-31 por **Paul Gibby**) — ominous toll, embrace ursur, sonsuming appetite
* `4aecabe2f` (2026-08-31 por **PvtVoid**) — Standardize the border-radius
* `34c0e1068` (2026-08-31 por **PvtVoid**) — Reimplement link auth key to players account
* `4122d2f58` (2026-08-31 por **PvtVoid**) — Give 10 replay saved by default to contributor instead of the 3
* `a5f4527fa` (2026-08-31 por **PvtVoid**) — Fix replay not properly displaying both players name
* `cd6239503` (2026-08-31 por **PvtVoid**) — Fix log not showing player name due to typo
* `0db86240d` (2026-08-31 por **PvtVoid**) — Fix turn 0 post-game stats
* `45b84f2fb` (2026-08-31 por **PvtVoid**) — Fix php error logs
* `944adc2d2` (2026-08-31 por **PvtVoid**) — Yellow and Blue Omnious Toll + Embrace of Ursur
* `ab09b60f1` (2026-08-30 por **Paul Gibby**) — reach of the abyss prototype
* `044bbcb0f` (2026-08-30 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `4f5db2ed4` (2026-08-30 por **Paul Gibby**) — remove unneccessary includes after reverting
* `00c8bcb1f` (2026-08-30 por **Paul Gibby**) — Revert "Improve GameLogic.php with too many includes to improve performances"
* `fc153207c` (2026-08-30 por **PvtVoid**) — Revert "Link auth key to players account so we can join back our games from different browser or if we lose our authKey cookie"
* `3116a8f69` (2026-08-30 por **Paul Gibby**) — consuming appetite gives blasmo go again
* `4fb4d2a4f` (2026-08-30 por **Paul Gibby**) — chains of consecration
* `f25887584` (2026-08-30 por **Paul Gibby**) — astral ambience + sigil of the muse
* `80f83fd25` (2026-08-30 por **Paul Gibby**) — consuming appetite prototype
* `9f12a9c42` (2026-08-30 por **Paul Gibby**) — always include sets under active development
* `4b1ac5bf0` (2026-08-30 por **Paul Gibby**) — consuming appetite starter
* `f1eb5ff4b` (2026-08-30 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `1981af625` (2026-08-30 por **Paul Gibby**) — refactor ironsong versus and beckoning light
* `7698e93d4` (2026-08-30 por **PvtVoid**) — Merge branch 'main' of https://github.com/Talishar/Talishar
* `8a14e07cc` (2026-08-30 por **PvtVoid**) — Revert "More backend php performance improvements"
* `17bc6c426` (2026-08-30 por **Paul Gibby**) — disable embrace ursur until image
* `85b561e55` (2026-08-30 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `b0e2ff934` (2026-08-30 por **Paul Gibby**) — embrace ussur prototype
* `c5fe99e6f` (2026-08-30 por **PvtVoid**) — Link auth key to players account so we can join back our games from different browser or if we lose our authKey cookie
* `4278f0450` (2026-08-30 por **PvtVoid**) — More backend php performance improvements
* `0a14d6f4e` (2026-08-30 por **PvtVoid**) — Improve GameLogic.php with too many includes to improve performances
* `9388d589c` (2026-08-30 por **PvtVoid**) — Make some replay UI changes
* `c42c4675d` (2026-08-29 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `1befbbb81` (2026-08-29 por **Paul Gibby**) — ominous toll prototype
* `78b29ab65` (2026-08-29 por **PvtVoid**) — Build alt arts without the implode/explode round trip
* `23bcfbde1` (2026-08-29 por **PvtVoid**) — Fix Lesson Learned
* `9ef129701` (2026-08-29 por **Paul Gibby**) — remove debug line
* `22197cd3b` (2026-08-29 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `8e24fe1c9` (2026-08-29 por **Paul Gibby**) — fix lessons learned
* `51b260be5` (2026-08-29 por **PvtVoid**) — Revert "remove RemoveCardSameNames from lessons learned"
* `60d8d1e41` (2026-08-29 por **Paul Gibby**) — remove RemoveCardSameNames from lessons learned
* `3e197bd3e` (2026-08-29 por **Paul Gibby**) — astral ambience prototype
* `702080f08` (2026-08-29 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `1f205d60e` (2026-08-29 por **Paul Gibby**) — echoing trap stoke vengeance deadly spinneret
* `9463a4b05` (2026-08-29 por **PvtVoid**) — Talent and Class contains refactor and performance improvements
* `500b5d4d1` (2026-08-29 por **PvtVoid**) — Another batch of php performance improvements
* `3029efc41` (2026-08-28 por **Paul Gibby**) — fix vox necropolis with stolen corpses
* `4a8cb336d` (2026-08-28 por **Paul Gibby**) — rush of knowledge
* `afe0975c7` (2026-08-28 por **Paul Gibby**) — Merge branch 'main' of https://github.com/Talishar/Talishar into main
* `5680f2bd9` (2026-08-28 por **Paul Gibby**) — switch scorpio to tap for cost
* `504aaadbc` (2026-08-29 por **PvtVoid**) — Backend performance improvements
* `ed4b52b2d` (2026-08-28 por **Paul Gibby**) — sigil of the muse prototype
* `b36c5e4fa` (2026-08-28 por **Paul Gibby**) — make deadly spinneret interact correctly with ripple away
* `1de44a18e` (2026-08-28 por **Paul Gibby**) — deadly_spinneret prototype

</details>

<details>
<summary><b>Arquivos principais alterados upstream</b></summary>

- `.github/workflows/ci.yml`
- `.gitignore`
- `.htaccess`
- `AI/AIDebugger.php`
- `AI/AIHelpers.php`
- `AI/BotLogic.php`
- `AI/CardBehaviors.php`
- `AI/CombatDummy.php`
- `AI/EncounterAI.php`
- `AI/EncounterPlayLogic.php`
- `AI/EncounterPriorityLogic.php`
- `AI/EncounterPriorityValues.php`
- `AI/PlayerMacros.php`
- `APIs/APIParseGamefile.php`
- `APIs/AddFavoriteDeck.php`
- `APIs/BlockedUsersAPI.php`
- `APIs/ChangeDisplayNameAPI.php`
- `APIs/CheckPatreonAPI.php`
- `APIs/ChooseFirstPlayer.php`
- `APIs/CreateGame.php`
- *(e mais 383 arquivos...)*

</details>

#### Talishar Frontend
- **Transição de Versão**: `fa97acc11` (2026-09-12) ➔ `13afdb7b3` (2026-09-24)
- **Novos commits incorporados**: 87
- **Ações automáticas executadas**: Código upstream atualizado via fast-forward, Templates customizados reaplicados, Frontend Vite recompilado

<details>
<summary><b>Clique para ver a lista de commits incorporados</b></summary>

* `13afdb7` (2026-09-24 por **PvtVoid**) — Update ReplayPanel.module.css
* `53628a8` (2026-09-24 por **PvtVoid**) — Fix hand tap on preview
* `4506cfb` (2026-09-24 por **PvtVoid**) — Fix missing DFC
* `59979b4` (2026-09-24 por **PvtVoid**) — Fix duplicate of equipments in lobby being double selected
* `1ac2907` (2026-09-24 por **PvtVoid**) — Show error in the lobby if we can't confirm
* `7ba4be5` (2026-09-24 por **PvtVoid**) — Show manual button in dev mode
* `ee22e55` (2026-09-24 por **PvtVoid**) — Puzzle + snapshot feature
* `5564094` (2026-09-24 por **PvtVoid**) — Prompt Update
* `e654c10` (2026-09-24 por **PvtVoid**) — Drop the source image
* `3bfe460` (2026-09-23 por **PvtVoid**) — Don't show warning about not having equipment if there is no such equipment in the deck
* `f50656c` (2026-09-23 por **PvtVoid**) — Hide manual mode panel/toggle in private game
* `69e3ae0` (2026-09-23 por **PvtVoid**) — Add images to prompt + puzzle frontend update for mod page + Add Viserai Usurper back marvelmarvel match
* `bdd18fb` (2026-09-23 por **PvtVoid**) — Add puzzle tab to mod page
* `eed45e1` (2026-09-23 por **PvtVoid**) — Sort choosemultizone and other popUp + make the popUp fit 3 row
* `46525a6` (2026-09-22 por **PvtVoid**) — Add a PromptStats to mod page for future analyzes
* `ec792bd` (2026-09-22 por **PvtVoid**) — Add Vynnset gem
* `8cf21cf` (2026-09-22 por **PvtVoid**) — Update to remove ads links
* `d3df542` (2026-09-22 por **PvtVoid**) — Add ad rails to navigation pages
* `20c5d51` (2026-09-22 por **PvtVoid**) — Fix ads not showing in the EndGameStats anymore
* `12defb3` (2026-09-22 por **PvtVoid**) — Fix userDropdownMenu anchor so they all match. Looks cleaner
* `c4b4965` (2026-09-22 por **PvtVoid**) — Update loadingTrivia.ts
* `689d22b` (2026-09-22 por **PvtVoid**) — Update LandmarkZone.module.css
* `8c6ad41` (2026-09-22 por **PvtVoid**) — Contracts Completed Stat
* `e77a3d9` (2026-09-22 por **PvtVoid**) — Undo tilt change
* `4064dde` (2026-09-22 por **PvtVoid**) — Add purple to displays on the website as a valid pitch color/value
* `7029ecc` (2026-09-22 por **PvtVoid**) — Add purple to purple cards + fix tilt on current turn effects
* `76c99f1` (2026-09-21 por **PvtVoid**) — Don't make the whole div clickable in the end game stats
* `3dba91a` (2026-09-21 por **PvtVoid**) — Fix label test missing a color
* `134f7e2` (2026-09-20 por **PvtVoid**) — Don't show manual mode if it was open in a previous game where it was legal
* `6a57cdb` (2026-09-20 por **PvtVoid**) — Try to fix equipping modular on mobile on chrome/Safari
* `76432b5` (2026-09-20 por **PvtVoid**) — Add NoFirst option to stats so people can include turn 0 if they want
* `9b0235e` (2026-09-20 por **PvtVoid**) — Merge both PlayerGrid into 1 component + refactor descriptions
* `bda38bc` (2026-09-19 por **PvtVoid**) — Update optionsSlice.ts
* `bdbac0e` (2026-09-19 por **PvtVoid**) — Clean FE stuff
* `5f961de` (2026-09-19 por **PvtVoid**) — Refactor zones, toast style, toggles and much more duplicated code
* `c16a251` (2026-09-19 por **PvtVoid**) — Hide Ad Blocked Detected for supporters
* `5a94fc5` (2026-09-18 por **PvtVoid**) — Small /Premium fix
* `463a73e` (2026-09-18 por **PvtVoid**) — Update Premium.tsx
* `a8d3880` (2026-09-18 por **PvtVoid**) — Refactoer RemoveAdsLink and duplicated settings tabBody
* `4f76bb6` (2026-09-18 por **PvtVoid**) — Update performanceMetrics.ts
* `6e087f2` (2026-09-18 por **PvtVoid**) — Fix issue with video ad not showing
* `6eccb69` (2026-09-18 por **PvtVoid**) — More frontend refactors
* `1d0411e` (2026-09-18 por **PvtVoid**) — Refactors our three charts in EndGameStats
* `2c10371` (2026-09-18 por **PvtVoid**) — Refactor floating pop ups into one component
* `ce80994` (2026-09-18 por **PvtVoid**) — Refactor all equipment zones from one component copied four times
* `0c150b7` (2026-09-18 por **PvtVoid**) — Refactor RearrangeTopInput and TriggerOrderInput being the same code almost
* `bca49ee` (2026-09-18 por **PvtVoid**) — Show equipped arena cards on hero + remove logs
* `7b7b27b` (2026-09-18 por **PvtVoid**) — Update labels css
* `e1804e7` (2026-09-18 por **PvtVoid**) — Remove primary borders
* `54e31db` (2026-09-18 por **PvtVoid**) — Fix typo
* `e57edb7` (2026-09-18 por **PvtVoid**) — Refactor new pre-game functions to one unready(action, failureKey).
* `9480495` (2026-09-18 por **PvtVoid**) — Remove unreachable early return in Lobby
* `c286d57` (2026-09-18 por **PvtVoid**) — Update HeroVsHeroIntro.tsx
* `f304861` (2026-09-18 por **PvtVoid**) — Update InProgressGame.module.scss
* `4b42437` (2026-09-18 por **PvtVoid**) — Update mastery in-game and lobby + subcards counters hidden
* `fed3ad8` (2026-09-18 por **PvtVoid**) — Hide collumns with 0 everywhere in End Game stats
* `fe58e06` (2026-09-18 por **PvtVoid**) — Arena -> Equipment wording
* `599daaf` (2026-09-17 por **PvtVoid**) — Help users with new lobby presence
* `dc4d503` (2026-09-17 por **PvtVoid**) — Remove useless tooltip
* `119a12b` (2026-09-17 por **PvtVoid**) — Manual surge creation for Valda setting
* `0ade972` (2026-09-17 por **PvtVoid**) — Hide deck tab on pre-selection
* `28dc0e0` (2026-09-17 por **PvtVoid**) — Show first player without checking chat
* `5e3d6f9` (2026-09-17 por **PvtVoid**) — Update Lobby.tsx
* `91cc715` (2026-09-17 por **PvtVoid**) — Fix pre-game procedure
* `e511c24` (2026-09-17 por **PvtVoid**) — New pre-game procedure
* `6c04c17` (2026-09-16 por **PvtVoid**) — ShowLayerGoAgain setting
* `3134735` (2026-09-16 por **PvtVoid**) — Fix Keyword + CardPortal inconsistency
* `1395429` (2026-09-16 por **PvtVoid**) — Fix frontend going without value in settings
* `3092028` (2026-09-16 por **PvtVoid**) — Show go again on layer
* `3a4f5e2` (2026-09-16 por **PvtVoid**) — Fix mobiles issues
* `6336a0c` (2026-09-15 por **PvtVoid**) — Leaving a lobby is silent again instead of error "0"
* `8264edc` (2026-09-15 por **PvtVoid**) — Update SettingsPanel.module.css
* `bc92e10` (2026-09-15 por **PvtVoid**) — Revert "Make replay links more visually attractive"
* `6fe10ae` (2026-09-15 por **PvtVoid**) — Make replay links more visually attractive
* `3218af9` (2026-09-15 por **PvtVoid**) — Make settings work across devices + rework settings UI
* `d6eb15c` (2026-09-15 por **PvtVoid**) — Allow users to turn on/off all gates/auras gems at once
* `a363a4c` (2026-09-14 por **PvtVoid**) — Add Patreon to isSupporter on profile page
* `07b1ac6` (2026-09-14 por **PvtVoid**) — Fix timers in private game
* `0d95506` (2026-09-13 por **PvtVoid**) — Add a "always wager" gem to Olympia
* `a2be6b6` (2026-09-13 por **PvtVoid**) — Fix mouse hovering issue
* `4e49fc9` (2026-09-13 por **PvtVoid**) — Add Manual Valiant Dynamo setting
* `75d08fb` (2026-09-13 por **PvtVoid**) — Fix mobile issue in lobby to unequip cards
* `b4c93a3` (2026-09-13 por **PvtVoid**) — Fix equipment not unequiping on mobile
* `524f05d` (2026-09-13 por **PvtVoid**) — Update GridBoard.module.css
* `40b05d7` (2026-09-13 por **PvtVoid**) — Remove unused processinputs
* `f2dd2ea` (2026-09-12 por **OotTheMonk**) — Merge pull request #798 from Talishar/show-top-spectators
* `c8e00d6` (2026-09-12 por **OotTheMonk**) — Show top spectators

</details>

<details>
<summary><b>Arquivos principais alterados upstream</b></summary>

- `index.html`
- `public/locales/en/translation.json`
- `public/locales/fr/translation.json`
- `public/locales/ja/translation.json`
- `public/locales/zh/translation.json`
- `scripts/backend-keyword-map-generator.js`
- `scripts/cr-text-generator.js`
- `scripts/keyword-map-generator.js`
- `src/app/GameStateHandler.test.tsx`
- `src/app/GameStateHandler.tsx`
- `src/app/ParseGameState.test.ts`
- `src/app/ParseGameState.ts`
- `src/appConstants.test.ts`
- `src/appConstants.ts`
- `src/components/AdBlockingRecovery/AdBlockingRecovery.tsx`
- `src/components/ImageSelect/ImageSelect.tsx`
- `src/components/LanguageSelector/LanguageSelector.module.css`
- `src/components/LanguageSelector/LanguageSelector.tsx`
- `src/components/RemoveAdsLink/RemoveAdsLink.module.css`
- `src/components/RemoveAdsLink/RemoveAdsLink.tsx`
- *(e mais 191 arquivos...)*

</details>

