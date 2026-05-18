# Human

Assistant CLI local pour construire un clone de style d'ecriture a partir d'exports Discord.

Le projet reste local par defaut: les exports bruts vont dans `data/raw/`, les fichiers traites dans
`data/processed/`, et ces deux dossiers sont ignores par Git sauf leurs `.gitkeep`.

## Ce que fait la V1

- ingere des exports JSON DiscordChatExporter;
- anonymise pseudos, noms visibles, emails, telephones, URLs, invitations Discord, IDs Discord, channels et adresses simples;
- marque tes messages avec `is_target=true`;
- construit un dataset ou les autres personnes ne servent que de contexte;
- garde tes fautes, abreviations et messages courts dans les reponses cibles;
- produit une sortie modele attendue en JSON: `{"messages":["message 1","message 2"]}`;
- appelle n'importe quel endpoint OpenAI-compatible, dont un serveur local Qwen3.6-27B.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Parler a l'assistant

Le plus simple:

```cmd
scripts\human-menu.cmd
```

Ou direct avec le chat complet:

```cmd
scripts\chat-full.cmd
```

Mode offline immediat, sans modele:

```cmd
scripts\chat-mock.cmd
```

Mode modele local Qwen3.6 quantifie via `C:\Users\teamr\Desktop\ai\llama\llama-server.exe`:

```cmd
scripts\chat.cmd
```

Dans le chat:

- tape ton message puis entree;
- `/reset` vide l'historique de la session;
- `/exit` quitte.
- l'etat social/emotionnel est stocke localement dans `state/social_state.json`.

Le CLI selectionne automatiquement des exemples proches dans
`data/processed/conversations.cleaned.jsonl` a chaque message. Ca evite d'envoyer
toujours les memes fewshots et limite les reponses generiques.
Il ajoute aussi des signaux locaux au prompt: langue detectee (`fr`, `en`, `mixed`),
intention courte (`tfq`, `pq`, salutation, question), abreviations connues, et regles anti-echo.
Il injecte enfin un background local: planning, activite actuelle probable, disponibilite et reactions
aux taunts comme "pas de vie". Le fichier prive est `config/background.json`, ignore par Git.
Pour desactiver ce comportement:

```powershell
python -m src.cli --chat --no-dynamic-fewshots --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b --no-response-format
```

## Moteur social local

Le CLI maintient une memoire locale par personne et conversation:

- etat emotionnel evolutif: energie, attention, stress, patience, playfulness, affection, irritation, curiosity;
- memoire personne: relation, familiarite, trust, warmth, irritation, derniers contacts;
- memoire conversation: derniers messages et timestamps;
- analyse du message: `addressing_bot`, `intent`, `tone`, `urgency`, `reply_expected`;
- decision: `should_reply`, `delay_seconds`, `reply_style`, `max_messages`, `emotional_color`.

Options utiles pour preparer le futur bot Discord:

```powershell
python -m src.cli --chat `
  --user-id "discord_user_id" `
  --display-name "Pseudo" `
  --conversation-id "dm_or_channel_id" `
  --bot-name "human" `
  --mentioned `
  --server-channel
```

En DM, le bot considere qu'on lui parle. En serveur, il observe par defaut et ne repond que si mentionne,
adresse directement, ou si l'intention le justifie. Pour tester sans modele:

```powershell
python scripts/simulate_social.py --reset
```

La memoire reste locale dans `state/`, ignoree par Git.

## Scripts Windows utiles

- `scripts\human-menu.cmd` : menu complet.
- `scripts\chat-full.cmd` : lance Qwen3.6 quantifie puis ouvre le chat social complet.
- `scripts\chat.cmd` : alias court du chat Qwen3.6.
- `scripts\chat-mock.cmd` : chat offline sans modele.
- `scripts\server-start-fast.cmd` : Qwen3.6 `IQ2_XXS`, plus rapide.
- `scripts\server-start-quality.cmd` : Qwen3.6 `IQ2_M`, un peu plus qualitatif.
- `scripts\server-check-mtp.cmd` : verifie si ton `llama-server.exe` supporte `--spec-type draft-mtp`.
- `scripts\install-llama-mtp.cmd` : installe/maj llama.cpp CUDA side-by-side dans `C:\Users\teamr\Desktop\ai\llama-mtp`.
- `scripts\server-start-mtp.cmd` : lance `unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL` si llama.cpp est assez recent.
- `scripts\chat-mtp.cmd` : chat complet avec le serveur MTP.
- `scripts\server-status.cmd` : process, API, GPU.
- `scripts\server-stop.cmd` : stoppe `llama-server.exe`.
- `scripts\pipeline-rebuild-all.cmd` : regenere ingestion/anonymisation/datasets/fewshots/eval.
- `scripts\discord-exporter.cmd` : ouvre DiscordChatExporter et rappelle de sauvegarder dans `data\raw`.
- `scripts\social-sim.cmd` : simulation multi-personnes.
- `scripts\eval-mock.cmd` : evaluation locale mock.
- `scripts\eval-qwen.cmd` : evaluation locale avec Qwen.
- `scripts\open-reports.cmd` : ouvre les rapports locaux.
- `scripts\probe-chat.cmd` : lance des conversations synthetiques et produit `reports/chat_probe.*`.
- `scripts\activity-now.cmd` : affiche le background/activite locale injectee au prompt.

Commande directe sans launcher:

```powershell
python -m src.cli --chat --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b --no-response-format
```

Copie `.env.example` vers `.env` si ton shell ne fournit pas deja ces variables:

```powershell
$env:OPENAI_BASE_URL="http://127.0.0.1:8080/v1"
$env:OPENAI_API_KEY="yourbot-local"
$env:OPENAI_MODEL="qwen3.6-27b"
```

## Workflow local

Le chemin rapide:

1. Ouvre DiscordChatExporter avec `scripts\discord-exporter.cmd` ou l'option 12 du menu.
2. Exporte chaque conversation au format JSON dans `data/raw/`, avec un nom de fichier distinct.
3. Lance `scripts\pipeline-rebuild-all.cmd` pour reconstruire le dataset prive complet.

En manuel:

1. Mets tes exports DiscordChatExporter JSON dans `data/raw/`.
2. Ingestion:

```powershell
python scripts/ingest_discord.py --input data/raw --output data/processed/ingested.jsonl
```

3. Anonymisation, en indiquant ton pseudo ou ton ID Discord exact:

```powershell
python scripts/anonymize.py `
  --input data/processed/ingested.jsonl `
  --output data/processed/anonymized.jsonl `
  --target-author "TonPseudo"
```

Tu peux ajouter un fichier prive de termes sensibles, non committe, par exemple `data/raw/private_terms.txt`:

```powershell
python scripts/anonymize.py `
  --input data/processed/ingested.jsonl `
  --output data/processed/anonymized.jsonl `
  --target-author-id "123456789012345678" `
  --terms-file data/raw/private_terms.txt
```

## Abreviations et slang local

Le fichier suivi `config/abbreviations.example.json` montre le format. Pour ajouter tes propres raccourcis
sans les publier, cree `config/abbreviations.json`; ce fichier est ignore par Git.

```json
{
  "abbreviations": {
    "tfq": "tu fais quoi",
    "pq": "pourquoi",
    "cdq": "c'est quoi"
  }
}
```

## Background et activites

Le fichier suivi `config/background.example.json` sert de modele. Pour rendre le clone plus coherent,
cree `config/background.json` et mets-y ton vrai planning local, tes activites plausibles, tes reactions
aux piques, et ce qu'il ne doit jamais inventer. Ce fichier est ignore par Git.

Voir l'activite actuelle injectee au prompt:

```cmd
scripts\activity-now.cmd tfq
```

Le CLI s'en sert pour eviter les reponses creuses du type `je vis dans ma vie`: quand on demande `tfq`,
il pioche dans l'activite actuelle; quand on le taunt, il utilise une reaction courte.

4. Dataset:

```powershell
python scripts/build_dataset.py `
  --input data/processed/anonymized.jsonl `
  --output data/processed/dataset.jsonl
```

Pour produire directement le format nettoye demande pour le style personnel:

```powershell
python scripts/build_cleaned_conversations.py `
  --input data/raw `
  --output data/processed/conversations.cleaned.jsonl `
  --target-user-id "123456789012345678"
```

Chaque ligne de `conversations.cleaned.jsonl` suit ce format:

```json
{"conversation_id":"discord_000001","context":[{"speaker":"PERSON_A","text":"ME tu check <URL> ?"}],"target_messages":["ouais j'arrive","2 sec jsp"],"meta":{"source":"discord","timestamps":["2026-01-01T10:00:30+00:00","2026-01-01T10:01:00+00:00"]}}
```

Dans ce format:

- toi = `ME`;
- les autres participants = `PERSON_A`, `PERSON_B`, etc.;
- les autres ne sont jamais dans `target_messages`, seulement dans `context`;
- tes messages consecutifs proches dans le temps sont regroupes en reply bursts;
- emails, telephones, URLs, invitations, mentions, IDs Discord et lieux evidents sont masques;
- le texte n'est pas corrige, donc les fautes et abreviations restent telles quelles.

5. Profil de style:

```powershell
python scripts/build_style_profile.py `
  --input data/processed/anonymized.jsonl `
  --output data/processed/style_profile.json
```

6. Fewshots locaux pour le CLI:

```powershell
python scripts/build_fewshot_examples.py `
  --input data/processed/conversations.cleaned.jsonl `
  --output data/processed/fewshot_examples.json `
  --limit 12
```

7. CLI avec un endpoint OpenAI-compatible:

```powershell
python -m src.cli `
  --base-url http://127.0.0.1:8080/v1 `
  --api-key yourbot-local `
  --model qwen3.6-27b `
  --no-response-format `
  --style-profile data/processed/style_profile.json `
  --fewshots data/processed/fewshot_examples.json `
  "il a dit quoi du coup ?"
```

ou apres installation editable:

```powershell
human-style --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b --no-response-format "tu peux repondre a ca ?"
```

Par defaut, le CLI affiche les messages un par un, comme Discord. Pour recuperer le JSON strict:

```powershell
python -m src.cli --mock --json "tu peux check ?"
```

Options utiles:

- `--temperature 0.7`
- `--top-p 0.9`
- `--max-tokens 512`
- `--no-think` pour insister sur aucune trace de raisonnement visible;
- `--think` si tu veux autoriser un raisonnement interne, sans changer la sortie visible;
- `--mock` pour tester offline sans modele;
- `--history history.txt` ou plusieurs `--context "PERSON_A: ..."` pour passer un historique recent.

Serveur Qwen3.6 quantifie deja configure:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_qwen36_server.ps1
python -m src.cli --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b --no-response-format "tu rep quoi ?"
```

Par defaut, `start_qwen36_server.ps1` utilise:

- `C:\Users\teamr\Desktop\ai\llama\llama-server.exe`
- `C:\Users\teamr\Desktop\ai\llama\models\Qwen3.6-27B-UD-IQ2_XXS.gguf`

### Qwen3.6 MTP Unsloth

Unsloth indique que les GGUF MTP peuvent accelerer l'inference via llama.cpp avec:

```powershell
llama-server -hf unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL `
  -ngl 99 -c 8192 -fa on -np 1 `
  --spec-type draft-mtp --spec-draft-n-max 6
```

Dans ce repo:

```cmd
scripts\server-check-mtp.cmd
scripts\install-llama-mtp.cmd
scripts\server-start-mtp.cmd
scripts\chat-mtp.cmd
```

Si `server-check-mtp.cmd` dit que `draft-mtp` n'est pas supporte, ton binaire llama.cpp est trop vieux.
`install-llama-mtp.cmd` telecharge le dernier build Windows CUDA depuis les releases officielles llama.cpp
dans `C:\Users\teamr\Desktop\ai\llama-mtp` sans ecraser ton dossier `ai\llama`.
Le mode fast classique reste dispo avec `scripts\server-start-fast.cmd`.
- port `8080`
- alias modele `qwen3.6-27b`

Autres endpoints OpenAI-compatible restent possibles, par exemple vLLM/SGLang:

```powershell
python -m src.cli --base-url http://127.0.0.1:8000/v1 --model autre-modele "il veut quoi lui ?"
```

Le CLI ne loggue pas les prompts, les fewshots, ni le dataset. Les erreurs endpoint sont tronquees.

## Evaluation

`scripts/evaluate_style.py` attend un JSONL de predictions, par exemple:

```json
{"messages":["ouais jsp","je regarde apres"]}
```

Commande:

```powershell
python scripts/evaluate_style.py `
  --style-profile data/processed/style_profile.json `
  --predictions data/processed/predictions.jsonl `
  --output data/processed/evaluation.json
```

Le rapport ne contient que des compteurs et scores, pas d'extraits longs.

## Evaluation locale du style

Pour construire un fichier d'evaluation depuis les conversations nettoyees:

```powershell
python scripts/build_eval_split.py `
  --input data/processed/conversations.cleaned.jsonl `
  --output data/processed/eval.jsonl `
  --limit 100
```

Pour generer des reponses avec le mock offline et produire les rapports:

```powershell
python scripts/run_style_eval.py `
  --eval data/processed/eval.jsonl `
  --mock `
  --blind-review
```

Pour utiliser un endpoint OpenAI-compatible:

```powershell
python scripts/run_style_eval.py `
  --eval data/processed/eval.jsonl `
  --base-url http://127.0.0.1:8080/v1 `
  --api-key yourbot-local `
  --model qwen3.6-27b `
  --temperature 0.7 `
  --top-p 0.9 `
  --blind-review
```

Sorties locales:

- `reports/eval_style.md`
- `reports/eval_style.json`
- `reports/blind_review.jsonl` si `--blind-review` est active

Les metriques couvrent longueur moyenne, nombre de messages par reponse, abreviations,
ponctuation, signaux francais/anglais, similarite lexicale et tics de langage.
Les rapports ne contiennent que des statistiques et des micro-extraits tronques.

## Format dataset

Chaque ligne de `dataset.jsonl` ressemble a ceci:

```json
{"id":"example_000001","input":{"context":[{"author":"<USER_0001_abcd12>","content":"tu viens ?"}],"instruction":"Reponds comme le compte cible. Retourne uniquement un JSON {\"messages\": [..]}."},"output":{"messages":["ouais j'arrive","2 sec"]},"meta":{"target_message_count":2,"last_timestamp":"2026-01-01T10:00:03Z"}}
```

Les messages des autres personnes apparaissent seulement dans `input.context`.
Les messages a apprendre sont uniquement dans `output.messages`, et seulement quand `is_target=true`.

## Adapter un autre format Discord

La couche d'adaptation est dans `src/discord_export.py`.
Pour un autre export, ajoute une fonction de parsing qui retourne les memes champs normalises:

- `timestamp`
- `author_id`
- `author_name`
- `author_display_name`
- `content`
- `channel_id` / `channel_name`
- `source_message_id`

Le reste du pipeline n'a pas besoin de connaitre le format source.

## Securite et hygiene Git

- `data/raw/*` et `data/processed/*` sont ignores.
- Ne committe pas `.env`.
- Les scripts affichent des compteurs, pas de longs extraits prives.
- Verifie toujours `git status --short` avant de pousser.
- Pour partager le projet, partage le code et des exemples factices, jamais tes exports ni tes datasets.
