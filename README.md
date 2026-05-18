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

Copie `.env.example` vers `.env` si ton shell ne fournit pas deja ces variables:

```powershell
$env:OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
$env:OPENAI_API_KEY="local-not-needed"
$env:OPENAI_MODEL="qwen3.6-27b"
```

## Workflow local

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

6. CLI avec un endpoint OpenAI-compatible:

```powershell
python -m src.cli --style-profile data/processed/style_profile.json "il a dit quoi du coup ?"
```

ou apres installation editable:

```powershell
human-style --style-profile data/processed/style_profile.json "tu peux repondre a ca ?"
```

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
