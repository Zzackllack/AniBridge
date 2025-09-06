---
title: Legal Disclaimer
outline: deep
---

# AniBridge — Legal Notice and Global Disclaimer

Version: 2025-08-24

Important: Please read this entire notice carefully before installing, running, contributing to, or interacting with the AniBridge project and any related artifacts (source code, binaries, Docker images, configuration, documentation). By using this software you acknowledge and agree to the terms below. If you do not agree, do not use the software.

1) No Hosting, No Content Provision, No Endorsement

- AniBridge is an automation bridge and API compatibility layer built on FastAPI. It exposes synthetic Torznab and qBittorrent-compatible endpoints to integrate with automation tools (e.g., Prowlarr, Sonarr). It does not host, store, seed, mirror, upload, or otherwise provide any audiovisual works or copyrighted content.
- The project’s “magnet-like” identifiers are synthetic metadata for internal job routing. They are not links to BitTorrent swarms and do not initiate peer-to-peer distribution. The qBittorrent “shim” exists solely to satisfy client APIs and does not join or seed any BitTorrent network.
- AniBridge may programmatically request data or files from third-party websites or file hosts only at the explicit direction of the end user and subject to the user’s configuration. The maintainers neither curate nor supply any catalog of content, links, or sources.
- This project is not affiliated with, endorsed by, or sponsored by any third-party service, including “AniWorld,” its operators, or any hosting providers referenced by configuration or code (e.g., VOE, Doodstream, Filemoon, Streamtape, etc.). All names and trademarks belong to their respective owners and are used solely for identification and interoperability discussion.

2) User Responsibility and Compliance

- You are solely responsible for how you use AniBridge. You must ensure that your use is lawful in your jurisdiction and complies with all applicable laws, regulations, and court orders, as well as the terms of service and acceptable use policies of any third-party sites or services you access through this software.
- Many jurisdictions prohibit the unauthorized reproduction, communication, public performance, making available, or distribution of copyrighted works. Some jurisdictions also prohibit downloading from obviously unlawful sources, and/or the circumvention of technical protection measures (DRM/TPMs). You must not use AniBridge for any unlawful purpose.
- If you use this software to access or download from third-party services, you must have a valid legal basis (e.g., your own licensed copy, public domain, explicit permission from the rights holder). Personal-use, educational, or “private copy” concepts are not universal and often very limited. Do not assume that “streaming” implies a right to download.
- Respect robots.txt, rate limits, CAPTCHAs, and access controls. Do not attempt to bypass paywalls, digital rights management, or other technical protection measures. Do not scrape where terms of service prohibit it. Your configuration and actions determine compliance.

3) No Legal Advice; Consult Counsel

- Nothing in this repository, its documentation, or community communications constitutes legal advice. Laws vary significantly by country/state and change over time. If you are unsure about the legality of your use case, consult a qualified attorney licensed in your jurisdiction.

4) Jurisdiction-Specific, Non-Exhaustive Notes

- United States (US): Unauthorized reproduction, distribution, or public performance of copyrighted works may violate Title 17 of the U.S. Code. Anti-circumvention prohibitions under the DMCA (17 U.S.C. § 1201) may apply even where an underlying use might otherwise be fair. “Fair use” is a narrow, fact-specific defense and not a general permission.
- European Union (EU): The Infosoc Directive and related national implementations protect rightholders and prohibit circumvention of technological measures. Limited private-copy exceptions may exist but typically exclude copies made from obviously unlawful sources and do not authorize circumvention.
- Germany (DE): Private copies are narrowly permitted under the German Urheberrechtsgesetz (UrhG) subject to strict conditions (e.g., no copy from an obviously unlawful source, no circumvention). Do not rely on “Privatkopie” for content obtained from untrusted sources or via technical measure bypass.
- United Kingdom (UK): A general private-copy exception has been curtailed or repealed; private copying without permission is typically not permitted. Anti-circumvention and rightholder protections remain robust under UK law.
- Other Jurisdictions: Local copyright, communications, and computer misuse laws may impose additional obligations or prohibitions (including criminal liability). It is your duty to know and comply with the laws applicable to you.

5) Third-Party Services, Terms, and “AniWorld” Disclaimer

- AniBridge can be configured to interact with third-party sites and hosting providers. Each such service has its own terms, policies, and rights-management practices. The availability or technical possibility to download content does not imply permission.
- “AniWorld” and similar platforms may operate in legal gray areas or jurisdictions with inconsistent enforcement. AniBridge does not operate, partner with, or endorse such services. References in the codebase exist solely for technical interoperability by end users who accept full responsibility for compliance.
- If a third-party service’s terms prohibit automated access, scraping, or downloading, you must not configure AniBridge to do so. This project does not provide or condone any means to defeat paywalls, authentication gates, or DRM.

5.1) AniWorld Terms (“Nutzungsbedingungen”) and DMCA

- AniWorld publishes site rules/terms at https://aniworld.to/support/regeln. Among other things, those terms state that automated scraping, automated extraction or manipulation of content and datasets is not permitted, and that AniWorld may seek damages and take further measures against violations. Do not configure or use AniBridge in any way that would violate those terms.
- AniWorld provides a DMCA takedown process at https://aniworld.to/dmca and a contact/support channel at https://aniworld.to/account/support/new. If you are a rights holder and request removal of content from AniWorld or its hosts, you must contact AniWorld or the relevant hosting provider directly. AniBridge does not host or control third-party content and cannot remove materials from external services.
- AniWorld’s own terms include warranty and liability disclaimers and indicate a governing law outside of many users’ jurisdictions (reportedly Belize). Regardless of AniWorld’s internal terms, your obligations arise under the laws applicable to you, and you must comply with both the law and any third-party terms you accept.

5.2) Alignment with AniWorld-Downloader Library Disclaimer

- The community-maintained AniWorld Downloader library states that it is intended to access content already publicly available online, does not promote piracy or copyright violations, and that the developer is not responsible for how the tool is used or for external content. AniBridge adopts a similarly strict stance: it hosts nothing, promotes no infringement, and relies on user configuration. Legality depends on your specific use case, jurisdiction, and the terms of the services you access.
- The AniWorld-Downloader README further notes that the tool does not control the accuracy, legality, or availability of third-party websites. The same applies here: interoperability references in AniBridge do not imply control over, or endorsement of, third-party sites or their content.

6) Intellectual Property; No Infringement Intent

- This project is provided for interoperability, research, and automation workflows with lawful content only. It must not be used to infringe any copyright, trademark, or other intellectual property rights.
- Contributors must not submit code primarily designed to enable or facilitate infringement, evasion of access controls, or circumvention of technological protection measures.

7) Data Handling, Privacy, and Logging

- By default, AniBridge can log operational events to local files under the `data/` directory (e.g., terminal logs). Logs may include file names, titles, URLs, or other identifiers provided by your configuration or third-party services.
- You are responsible for handling any logged or cached data in compliance with applicable privacy and data-protection laws (e.g., GDPR, CCPA) and with your own security policies. If you process personal data, define a lawful basis and implement appropriate safeguards.
- Do not share logs publicly if they may reveal personal data, credentials, or links to protected works.

8) No Warranty; Limitation of Liability

- THE SOFTWARE IS PROVIDED “AS IS” AND “AS AVAILABLE,” WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT. USE IS AT YOUR OWN RISK.
- TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL THE AUTHORS, MAINTAINERS, CONTRIBUTORS, OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT, STRICT LIABILITY, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OF, MISUSE OF, OR INABILITY TO USE THE SOFTWARE.
- WITHOUT LIMITATION, WE DISCLAIM LIABILITY FOR: (a) ANY COPYRIGHT OR OTHER IP INFRINGEMENT RESULTING FROM USER ACTIONS; (b) ANY VIOLATION OF THIRD-PARTY TERMS OF SERVICE; (c) ANY DATA LOSS, SERVICE INTERRUPTION, OR SECURITY INCIDENT; (d) ANY ADMINISTRATIVE, CIVIL, OR CRIMINAL PENALTIES INCURRED BY USERS.

9) Indemnification

- To the extent permitted by law, you agree to indemnify, defend, and hold harmless the authors, maintainers, contributors, and copyright holders from and against any and all claims, liabilities, damages, losses, and expenses (including reasonable attorneys’ fees) arising out of or in any way connected with: (a) your access to or use of the software; (b) your violation of this notice; (c) your infringement or alleged infringement of any intellectual property or other right of any person or entity; or (d) your breach of any applicable law or third-party terms.

10) Distribution, Forks, and Derivative Works

- If you distribute, fork, or build upon this project, you are responsible for ensuring that your distribution includes clear, prominent disclaimers of non-affiliation, non-endorsement, and non-hosting similar to those in this document, and that your distribution complies with all applicable laws and third-party terms.
- You may not represent your distribution as affiliated with or endorsed by this project’s maintainers or any referenced third party (including “AniWorld”) without express written permission from the relevant party.

11) Takedown and Abuse Reports (Repository Content Only)

- This project does not host third-party media. If you believe that material within this repository (e.g., code or documentation) infringes rights you own, please submit a report with sufficient detail to identify the allegedly infringing repository content. Do not send requests to remove or block third-party media located elsewhere; we have no control over external sites.
- Security or abuse concerns unrelated to intellectual property may be reported per the repository’s security policy. We reserve the right—but not the obligation—to remove or modify repository content at our discretion.
- For materials available on or through AniWorld or its file hosts, submit takedown requests via AniWorld’s DMCA channel at https://aniworld.to/dmca and/or to the relevant host. AniBridge cannot process or effectuate removals on third-party platforms.

12) Technical Protection Measures and Circumvention

- Do not use AniBridge to defeat or bypass DRM or any technical protection measures. Anti-circumvention laws (e.g., DMCA § 1201 in the US; EU anti-circumvention rules; similar provisions in many countries) may impose liability regardless of whether the underlying use might otherwise be permitted.
- The presence of libraries such as yt-dlp or references to third-party hosts in the codebase does not authorize circumvention or any prohibited access. You are responsible for configuring and using such tools only in lawful ways.

13) Operational Boundaries and Intended Behavior

- AniBridge’s Torznab feed and qBittorrent APIs are compatibility shims that surface metadata and job status for lawful automation workflows. They are not a public indexer or torrent client and do not provide a peer-to-peer transport.
- Downloads—if any—occur only via direct HTTP(S) requests to third-party hosts as directed by the user’s configuration and may be subject to those hosts’ terms, availability, and technical constraints.
- The project does not guarantee availability, reliability, or continued interoperability with any third-party service. Third-party sites may change without notice or block automated access.

14) Export Control and Sanctions

- You are responsible for ensuring that your use, distribution, and export of this software complies with all applicable export-control, sanctions, and embargo laws and regulations in your jurisdiction and in any jurisdiction from which you make the software available.

15) Community Conduct and Contributions

- All participation is subject to the project’s Code of Conduct. By contributing, you certify that your contributions do not include code primarily intended to infringe IP rights, evade access controls, or facilitate unlawful access to third-party content.
- Contributors should avoid embedding direct links to copyrighted materials and must not include credentials, cookies, or instructions for bypassing authentication, paywalls, or DRM.

16) Reservation of Rights; Changes to This Notice

- All rights not expressly granted are reserved. We may update or replace this notice from time to time. Material changes will be reflected by updating the version/date above. Your continued use after an update constitutes acceptance of the revised terms.

17) Contact and Attribution

- For security matters, see SECURITY.md for the current process. For general technical issues, use the repository’s issue tracker. We cannot assist with requests about external sites or third-party content.
- Acknowledgment: This project may interoperate with third-party libraries such as the community-maintained AniWorld Downloader library. Such interoperability does not imply any partnership, affiliation, or endorsement.

Summary (Non-Controlling): AniBridge is a developer tool and compatibility layer. It hosts nothing, seeds nothing, and offers no content. You are entirely responsible for your configuration and actions. Use only with content and sources you are legally permitted to access. No warranties. No liability. No affiliation with “AniWorld” or any third-party host.
