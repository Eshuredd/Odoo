# Locally bundled visual assets

- Plus Jakarta Sans Variable: distributed by `@fontsource-variable/plus-jakarta-sans`, SIL Open Font License 1.1. License: `public/licenses/Plus-Jakarta-Sans-OFL.txt`.
- Inter Variable: distributed by `@fontsource-variable/inter`, SIL Open Font License 1.1. License: `public/licenses/Inter-OFL.txt`.
- Lucide React icons: ISC license and included upstream notices, copied to `public/licenses/Lucide-LICENSE.txt`.

Font files are served from the local Next.js build; Lucide icons render as inline SVG. The SubCadence brand mark is a code-native SVG created for this implementation. No remote font, icon, avatar, or brand-image request is required at runtime. Other dependencies retain their licenses in their npm packages and the exact installed versions are recorded in package-lock.json.
