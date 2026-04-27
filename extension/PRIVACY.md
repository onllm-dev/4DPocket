# 4DPocket Chrome Extension — Privacy Policy

**Effective date: April 2026**

## What this extension does

4DPocket is a browser extension that lets you save web pages, highlighted text, and links to your own self-hosted 4DPocket knowledge base. The extension sends saved content only to the server URL you configure — a backend you run yourself, on hardware you control.

## Data collected

The extension collects only what you explicitly ask it to save:

- The URL and title of pages you choose to save
- Text you highlight and manually send to your knowledge base
- Your login token, stored in `chrome.storage.local` on your own device

The extension does not collect browsing history, page content you have not explicitly saved, passwords, form data, or any other personal information.

## Where your data goes

All data goes directly from your browser to the 4DPocket server URL you enter in the extension options. That server is self-hosted by you. No data is sent to the extension developer, to any analytics service, or to any third party of any kind.

The extension does not include telemetry, crash reporting, or usage tracking of any kind.

## Third-party services

None. The extension makes HTTP requests only to the server URL you configure.

## Authentication credentials

Your login token is stored in `chrome.storage.local` on your own device. It is never transmitted to any server other than your configured 4DPocket backend. The extension refuses to send your token over plain HTTP to non-localhost servers (see `extension/src/core/api-client.ts:67`).

## How to delete your data

- To stop the extension from accessing your backend: remove the server URL and token in the extension options page, or uninstall the extension.
- To delete saved content from your knowledge base: use the 4DPocket web interface or API to delete items. Your data lives on your own server, so you have full control.
- Uninstalling the extension removes all locally stored credentials from your browser.

## Changes to this policy

If this policy changes materially, a new version will be published with an updated effective date in this file and in the extension repository.

## Contact

4DPocket is open-source software. Questions about this policy can be raised as issues in the project repository.
