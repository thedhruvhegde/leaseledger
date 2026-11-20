# Listing photos

Lease Ledger shows a photo on a listing card (16:10 hero) and in the detail gallery **only when someone has the
right to show it**. A listing without photos shows its generated street-map thumbnail instead. Never add a photo
of a different building as a stand-in, and never add generated or edited images presented as the real property.

## Rights first

- **Use only images you have the right to use**: photos you took yourself, photos a property manager has given you
  permission to use (keep the email), or images under an explicit open license (e.g. CC BY on Wikimedia Commons)
  whose terms you follow.
- **Zillow, Apartments.com, Rent.com, Zumper and similar portals**: their photos are copyrighted (by the portal, the
  photographer or the landlord) and their terms of use prohibit scraping and reuse. Do not copy them.
- **A property's own website** (e.g. the building's marketing site) is the better source, *with permission* from the
  owner/manager. Credit them and link the page.
- When in doubt, take your own photo of the building exterior from the public sidewalk.

## How to add photos (no backend change)

1. Put the files in `web/public/photos/<listing-id>/` as `.jpg` or `.webp` (about 1600 px wide, under 400 KB).
   The listing id is the `id` in `data/listings/listings.json` (e.g. `university-towers-2br`).
2. Add an entry to `web/public/photos/manifest.json`:

```json
{
  "university-towers-2br": [
    {
      "file": "exterior.jpg",
      "credit": "Jane Doe (own photo)",
      "source_url": "https://example.com/where-the-photo-or-permission-lives",
      "license": "Used with permission"
    }
  ]
}
```

Other keys and forms:

- `"file": "some-folder/exterior.jpg"` (with a slash) points at `web/public/photos/some-folder/exterior.jpg`, so one
  file can serve several listing ids: repeat the entry under each id (e.g. the 1BR and 2BR plans of one tower).
- `"position": "center 30%"` sets the crop for the 16:10 card (use it for tall towers so the building, not the sky
  or the sidewalk, fills the frame). Allowed: `center`, `top`, `bottom`, `left`, `right` or percentages.
- `source_url` may be empty when the original source is still being confirmed; the credit is then shown unlinked.
- `_unassigned/` holds photos that are not attached to any listing. Never attach a photo to a listing it doesn't show.

`credit` is shown as "Photo: <credit>" on every card and gallery image, linked to `source_url`. Keep `license`
accurate ("Own photo", "Used with permission from …", "CC BY 4.0"). The manifest is merged client-side with any
`photos` the API returns (`Listing.photos`, same `{src, credit, source_url, license}` shape).

3. Rebuild (`npm run build`) or just reload the dev server. Different plans of the same building need their own
   entry (copy the entry for each listing id).

To remove a photo, delete its entry and file. If an owner asks for removal, do it right away.
