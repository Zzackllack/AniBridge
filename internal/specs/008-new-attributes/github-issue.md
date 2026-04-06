# [FEATURE] Emit Newznab language + subs attributes in AniBridge Torznab results (Sonarr supports subs now)

## Summary

Add Newznab/Torznab item attributes for **audio language** and **subtitle languages** to AniBridge’s Torznab feed results:

- `newznab:attr name="language" value="..."`
- `newznab:attr name="subs" value="..."`

This allows Sonarr to correctly classify releases by language (instead of mis-detecting e.g. German as Japanese for anime) and to use the newly-merged **Subtitles indexer flag** based on the `subs` attribute.

References:

- Newznab attributes list (includes `language` + `subs`): https://inhies.github.io/Newznab-API/attributes/
- Sonarr PR adding `subs` support / “Subtitles” indexer flag (merged into `v5-develop`): https://www.github.com/Sonarr/Sonarr/pull/8043
- Related Sonarr issue (now closed by the PR): https://www.github.com/Sonarr/Sonarr/issues/7625

### Problem / Motivation

AniBridge bridges streaming-site catalogs to a Torznab API for *arr automation. AniBridge releases commonly include language hints in the title (e.g. `GER`, `ENG.SUB`), but **Sonarr currently classifies many of these incorrectly** (e.g. German releases shown as “Japanese” or “English”) when the indexer feed does not explicitly provide language metadata.

Additionally, Sonarr recently merged support for the Newznab `subs` attribute, enabling a **Subtitles indexer flag** and related filtering/scoring workflows. AniBridge should provide `subs` so users can prefer/subselect subtitle-capable releases (especially for anime).

### Proposed Solution

For each `<item>` in the Torznab RSS feed returned by AniBridge, include:

1) **Audio language attribute**

```xml
<newznab:attr name="language" value="German" />
```

2) **Subtitles attribute**

```xml
<newznab:attr name="subs" value="German" />
```

Both attributes are defined in the Newznab spec and already consumed by Sonarr (with subs support now merged in Sonarr v5).

### Suggested Mapping Rules (example)

Given AniBridge release names like:

- `...GER-ANIWORLD`
- `...GER.SUB-ANIWORLD`
- `...ENG.SUB-ANIWORLD`

A simple initial mapping could be:

Title token(s) | language (audio) | subs
-- | -- | --
GER | German | (optional / empty)
GER.SUB | German | German
ENG | English | (optional / empty)
ENG.SUB | English | English

Notes:

- The values should match Newznab “Natural languages” expectations (e.g. German, English).
- If a release has multiple subtitle languages, subs can be a comma-separated list (e.g. "English, Spanish"), per the Newznab attribute examples.
- If AniBridge can determine subtitles more accurately from the source (instead of title tokens), that should be preferred.

### Example: Expected Torznab <item>

```xml
<item>
  <title>Rascal.Does.Not.Dream.of.Bunny.Girl.Senpai.S01E01.720p.WEB.H264.GER.SUB-ANIWORLD</title>
  <guid isPermaLink="false">...</guid>
  <link>...</link>

  <newznab:attr name="category" value="5000" />
  <newznab:attr name="size" value="123456789" />

  <!-- NEW -->
  <newznab:attr name="language" value="German" />
  <newznab:attr name="subs" value="German" />
</item>
```
