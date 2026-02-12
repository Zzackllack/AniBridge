---
title: Legal Disclaimer
outline: deep
---

# AniBridge Legal Notice, Risk Allocation, and Use Restrictions

Version: 2026-02-12  
Status: Recast and superseding prior documentation notice text

This document is a comprehensive legal-risk notice for AniBridge users, operators, deployers, contributors, and redistributors. It is intentionally formal and should be read in full before installation, configuration, network exposure, or operational use.

No disclaimer can legalize unlawful conduct, immunize users against enforcement, or override mandatory law. If your use case implicates copyrighted works, automated extraction, circumvention controls, or cross-border data transfer, obtain jurisdiction-specific legal advice before use.

## 1. Scope, Parties, and Defined Terms

For this notice:

- `Software` means the AniBridge codebase, built artifacts, containers, documentation, and configuration surfaces.
- `Service Interfaces` means AniBridge endpoints and compatibility layers, including Torznab-style and qBittorrent-compatible APIs.
- `Synthetic Magnet Descriptor` means AniBridge-generated `magnet:?` identifiers used for internal routing metadata, not as a representation of a public BitTorrent swarm.
- `Upstream Services` means all external sites, hosts, mirrors, indexes, and delivery endpoints accessed by user configuration (including AniWorld, SerienStream/s.to, megakino, and hosters referenced by those services).
- `User` means any person or entity installing, running, exposing, querying, integrating, or redistributing the Software.

Use of the Software constitutes acknowledgement of this notice and assumption of the risks allocated to the User herein, to the maximum extent permitted by applicable law.

## 2. Technical Characterization and Operational Boundaries

AniBridge is an interoperability and automation layer. It is not, in its designed operation, a public torrent index, a BitTorrent peer, or a content-hosting platform.

Current implementation characteristics include:

- Torznab-compatible feed generation.
- qBittorrent-compatible API emulation for *arr interoperability.
- internally generated descriptor identifiers (`xt=urn:btih:<hash>`) derived from metadata fields.
- direct upstream retrieval workflows (HTTP(S) and provider-resolution paths) rather than swarm participation.
- optional STRM artifact generation and optional proxy-mode streaming for playback workflows.

Accordingly:

- AniBridge does not represent that any referenced media is licensed, authorized, or lawfully distributable.
- AniBridge does not convey rights in any work.
- AniBridge does not assume custody or control of third-party legal entitlements.

## 3. Non-Affiliation, Trademark Separation, and No Endorsement

AniBridge is not affiliated with, endorsed by, sponsored by, or operated by any referenced upstream platform or host. Names, marks, and domains are used solely for identification, interoperability description, and user-initiated routing context. All third-party marks remain property of their respective owners.

## 4. User Compliance Obligations

The User bears exclusive responsibility for lawful operation, including but not limited to:

- ensuring a valid legal basis for access, copying, streaming, downloading, or storage;
- complying with copyright, neighboring-rights, anti-circumvention, computer misuse, and telecom regulations;
- complying with contractual restrictions (terms of service, robots policies, anti-automation clauses, and access controls);
- ensuring organizational compliance (employment policy, institutional policy, and internal controls);
- implementing safeguards against unauthorized access, abuse, or redistribution.

Prohibited use includes, without limitation:

- infringing reproduction, communication to the public, distribution, or making available;
- circumvention of DRM/TPMs or facilitation thereof;
- automated extraction where prohibited by upstream terms;
- operation for unlawful indexing, mass-exfiltration, or evasion workflows.

## 5. Multi-Jurisdiction Compliance Baseline (Non-Exhaustive)

The following references are provided as orientation only; they are not a complete legal map and do not replace counsel.

### 5.1 United States

Relevant U.S. framework includes:

- exclusive rights (17 U.S.C. § 106),
- fair use defense factors (17 U.S.C. § 107),
- anti-circumvention and trafficking prohibitions (17 U.S.C. § 1201),
- online service-provider safe harbor structure (17 U.S.C. § 512).

Users should not treat interoperability tooling as a blanket defense. Fair use is fact-intensive and post hoc; anti-circumvention can apply even where infringement is separately disputed.

### 5.2 European Union

Relevant EU framework includes:

- Directive 2001/29/EC (InfoSoc), including rights architecture and limits/exceptions regime;
- Article 6 anti-circumvention provisions in Directive 2001/29/EC;
- Directive (EU) 2019/790 (DSM), including platform-liability architecture;
- Regulation (EU) 2022/2065 (Digital Services Act), where applicable to intermediary-service roles.

The existence of technical access does not imply legal authorization. National implementations and enforcement practice remain decisive.

### 5.3 Germany

Users operating in or targeting Germany should review, at minimum:

- UrhG § 53 (private copies; restricted scope),
- UrhG § 95a (protection of technical measures),
- UrhG § 106 (criminally relevant unauthorized exploitation).

Do not presume that a private-copy theory validates copies from clearly unlawful sources or circumvention-enabled flows.

### 5.4 United Kingdom

Users operating in or targeting the UK should review, at minimum, the Copyright, Designs and Patents Act 1988 framework (including restricted acts and anti-circumvention-related provisions).

## 6. Upstream Terms and Provider-Specific Legal Friction

Provider-side legal constraints and platform terms are independently binding on Users.

Examples:

- AniWorld publishes platform terms/rules and a separate rights-holder/DMCA contact surface.
- s.to and related ecosystems have documented blocking/enforcement history in German-speaking markets.
- megakino and mirror ecosystems have documented domain-churn and enforcement pressure patterns.

Operational implication: technical reachability is not legal permission, and domain availability is not legal legitimacy.

## 7. Third-Party Video Hoster Layer and Control Limitations

Many upstream catalog/index services referenced by users (including AniWorld, s.to/SerienStream, and megakino ecosystems) generally do not represent themselves as the final storage layer for all video assets. In many workflows, they expose links, embeds, or player frames that route to separate video hosters or delivery networks.

Non-exhaustive hoster/domain labels that may appear in provider ecosystems include:

- `VOE`
- `Filemoon`
- `Streamtape` / `streamta.pe`
- `Vidmoly`
- `SpeedFiles`
- `Doodstream` / `d0000d`
- `LoadX`
- `Luluvdo`
- `Vidoza`
- `GXPlayer`

These names are included solely for identification and risk-allocation clarity. They are not endorsements, representations of ownership, or assertions of legal status.

### 7.1 Layered Responsibility Model

For legal and operational analysis, users should treat this ecosystem as a multi-layer chain:

- `Index/Portal Layer`: surfaces metadata, embeds, and outbound references.
- `Hoster/Delivery Layer`: may store, stream, or relay the underlying file/media segments.
- `User Automation Layer` (AniBridge + client stack): resolves references and performs user-initiated retrieval according to local configuration.

Liability, notice handling, and rights enforcement often differ by layer. A request directed to the wrong layer may be ineffective.

### 7.2 No Editorial, Custodial, or Takedown Authority by AniBridge

AniBridge maintainers do not control third-party catalogs, third-party hoster infrastructure, or their CDN edge systems. Accordingly, AniBridge has no unilateral legal or technical ability to:

- remove, delist, geo-block, or disable third-party hosted media;
- compel hosters to de-publish or preserve content;
- validate chain-of-title or license provenance for referenced media;
- guarantee persistence, deletion timing, or notice compliance by third parties.

AniBridge can only govern repository-controlled assets and software behavior within the AniBridge codebase itself.

### 7.3 Rights-Holder and Abuse Routing Implications

Where a rights-holder seeks content removal, de-indexing, or account-level enforcement, notices should be directed to the entity controlling the relevant layer:

- the upstream portal/index operator, if the complaint concerns indexing/embedding surfaces;
- the video hoster or delivery operator, if the complaint concerns hosted or streamed media;
- network intermediaries (as applicable under local law), where host-level escalation is required.

Notices sent exclusively to AniBridge cannot effect third-party content removal when AniBridge does not own or operate the target infrastructure.

### 7.4 User-Side Consequences

Because hoster control lies outside AniBridge:

- link availability may change without warning;
- provider pages may rotate hosters and mirrors;
- legal actions against portals/hosters may alter routing behavior abruptly;
- removal at hoster level may invalidate previously functional AniBridge workflows.

These outcomes are external-service effects, not a representation that AniBridge has assumed operational control over third-party media.

## 8. Rights-Holder Notices and Takedown Scope

AniBridge maintainers can address repository-contained material only (code/docs/repo assets). They cannot remove media hosted on third-party infrastructures and cannot execute takedowns for external services.

Rights holders must direct third-party content complaints to the relevant upstream platform or host and use the legal channels designated by those entities.

## 9. Privacy, Logs, and Data Governance

AniBridge may process and store operational metadata (job identifiers, paths, URLs, language/provider metadata, and diagnostics). Depending on deployment context, this can constitute personal data or commercially sensitive information.

The User is solely responsible for:

- lawful processing basis (e.g., GDPR/CCPA or local equivalent),
- retention controls and secure disposal,
- breach handling and disclosure obligations,
- redaction before publication of logs or diagnostics.

## 10. Warranty Disclaimer, Liability Exclusion, and Indemnity

THE SOFTWARE IS PROVIDED "AS IS" AND "AS AVAILABLE," WITHOUT EXPRESS OR IMPLIED WARRANTIES, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT, CONTINUITY, OR REGULATORY FITNESS.

TO THE MAXIMUM EXTENT PERMITTED BY LAW, AUTHORS, MAINTAINERS, CONTRIBUTORS, AND COPYRIGHT HOLDERS SHALL NOT BE LIABLE FOR DIRECT, INDIRECT, INCIDENTAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE LOSS, INCLUDING REGULATORY PENALTIES, BUSINESS INTERRUPTION, DATA LOSS, OR THIRD-PARTY CLAIMS ARISING FROM USE OR MISUSE.

The User agrees, to the maximum extent permitted by law, to indemnify and hold harmless maintainers and contributors from claims arising out of:

- unlawful operation;
- infringement allegations tied to user configuration or activity;
- violation of third-party terms;
- unauthorized access, data misuse, or circumvention conduct.

## 11. Export Controls, Sanctions, and Trade Restrictions

Users are responsible for compliance with applicable export-control, sanctions, embargo, and trade-restriction regimes in all relevant jurisdictions. AniBridge may not be used where such laws prohibit software transfer, access, technical assistance, or related services.

## 12. Contribution and Redistribution Conditions

Contributors and redistributors must not:

- market AniBridge as endorsed by third-party providers;
- package instructions primarily designed to bypass legal controls;
- remove or materially dilute legal-risk disclosures in downstream distributions.

Downstream redistributions should preserve prominent non-affiliation and lawful-use notices.

## 13. Severability, No Waiver, and Interpretive Priority

If any provision of this notice is unenforceable, the remainder remains in effect to the fullest extent permitted by law. Failure to enforce any part is not a waiver. If conflicts arise, mandatory law controls over this notice.

## 14. Amendments and Temporal Validity

This notice may be revised without prior notice to reflect legal, technical, provider, or enforcement changes. Users are responsible for reviewing the current version before continued operation.

## 15. No Legal Advice; Counsel Requirement for High-Risk Use

Nothing in AniBridge code, docs, issues, chats, or community channels is legal advice. For any potentially contentious workflow, consult qualified counsel licensed in your jurisdiction and familiar with copyright, platform liability, and anti-circumvention doctrine.

## 16. Selected Authorities and External Materials (Non-Exhaustive)

- [AniWorld Terms / Rules](https://aniworld.to/support/regeln)
- [AniWorld DMCA Contact Surface](https://aniworld.to/dmca)
- [CUII Public Recommendations](https://cuii.info/empfehlungen/)
- [17 U.S.C. § 106 (Cornell LII)](https://www.law.cornell.edu/uscode/text/17/106)
- [17 U.S.C. § 107 (Cornell LII)](https://www.law.cornell.edu/uscode/text/17/107)
- [17 U.S.C. § 1201 (Cornell LII)](https://www.law.cornell.edu/uscode/text/17/1201)
- [17 U.S.C. § 512 (Cornell LII)](https://www.law.cornell.edu/uscode/text/17/512)
- [Directive 2001/29/EC (EUR-Lex)](https://eur-lex.europa.eu/eli/dir/2001/29/oj/eng)
- [Directive (EU) 2019/790 (EUR-Lex)](https://eur-lex.europa.eu/eli/dir/2019/790/oj/eng)
- [Regulation (EU) 2022/2065 (DSA) (EUR-Lex)](https://eur-lex.europa.eu/eli/reg/2022/2065/oj/eng)
- [UrhG § 53 (gesetze-im-internet)](https://www.gesetze-im-internet.de/urhg/__53.html)
- [UrhG § 95a (gesetze-im-internet)](https://www.gesetze-im-internet.de/urhg/__95a.html)
- [UrhG § 106 (gesetze-im-internet)](https://www.gesetze-im-internet.de/urhg/__106.html)
- [UK Copyright, Designs and Patents Act 1988 (WIPO Lex)](https://www.wipo.int/wipolex/en/legislation/details/24241)

Accessed: 2026-02-12.
