---
name: c4-diagrams
description: Draw architecture diagrams in Lucidchart using the C4 model and Harry's dark design language (grouped regions, GCP product icons at the top-left of each box, cylinder datastores), then link or embed them from Confluence and the vault. Use whenever the user asks for an architecture, system context, container or component diagram, a C4 diagram, "draw this in Lucid", or a diagram for a Confluence or Obsidian page. Use it instead of ASCII art in any page that other people will read. Not for sequences that read fine as a numbered table, and not for Confluence whiteboards, which the Atlassian MCP cannot read or write.
---

# c4-diagrams

One diagram answers one question at one C4 level. Draw it in Lucidchart in the house style, keep a text twin of it, and link it from the page.

The reference image is `reference/component-diagram.png`, a component diagram for the Fuse SFTP connector. Read it before you draw. Match its **colour**, its **grouping** and its **GCP symbols at the top-left of each box**. Those three matter most.

## Pick the level

| Level | Shows | Boxes are | Use when |
| --- | --- | --- | --- |
| 1. System context | The system, its users and the other systems it touches | People, our system, external systems | The reader needs the boundary and the neighbours |
| 2. Container | What runs inside the system | Deployable units: services, jobs, topics, datastores | The reader needs to know what runs where |
| 3. Component | What is inside one container | Endpoints, modules, handlers | The reader needs to change or debug one service |
| 4. Code | Classes and functions | Almost never. Link to the code instead | |

The reference image mixes a few container-level items (topics, storage, VM) with the components of one Cloud Run service. That is acceptable only because the diagram is about one service and its immediate neighbours. Otherwise keep one level per diagram.

## C4 rules

- **Title and scope.** Name the level and the system, for example "Component diagram: sftp-connector". Say what the diagram does not show.
- **Every box has three things:** a name, a type or technology, and a short description. In the house style that is the bold title, the bold type prefix (`Pubsub topic:`, `Store:`, `Module:`) and the plain description.
- **Every arrow is one direction and has a label** that says what happens ("Push all file uploads"), not "uses". Add the protocol or technology when it helps.
- **Group by boundary.** A group is a system, a container or a deployment boundary (a VM, Cloud Run). Label it top-left. Never use a group only for tidiness.
- **Show external things outside the groups:** other systems, topics owned elsewhere, the people.
- **No unexplained colour, shape or icon.** Add a small key when the diagram uses anything beyond the table below.
- **Keep it small.** Aim for 20 boxes or fewer. If it needs more, split it by level or by flow.
- **Mark what you do not know.** Draw an unverified element or arrow with a dashed line and the label `Not confirmed`. Never draw a guess as fact.
- **Read left to right and top to bottom** where the flow allows. Avoid crossing lines.

## House style

Taken by sampling the pixels of `reference/component-diagram.png`.

| Element | Value |
| --- | --- |
| Canvas | `#1f1f21`, with a faint dot grid |
| Surface: groups, and boxes that sit outside a group | `#303134` |
| Box inside a group | `#242528` (darker than the group), with a 1 px `#1f1f21` edge |
| Border: groups and boxes outside a group | 1 px `#7e8188` |
| Connector | 1 px `#75787e`, open chevron arrowheads, right-angle bends. A gentle curve is acceptable where a bend would cross something |
| Text: titles, descriptions, group labels, edge labels | `#cecfd2`. Titles and type prefixes bold. Descriptions regular |
| Edge label | Small text sitting on the line, filled with the colour of whatever it sits on |
| GCP icon blues | `#aecbfa` (light), `#669df6` (mid), `#4285f4` (base) |

**Box anatomy.** About 225 by 120 px. The GCP icon sits at the top-left, about 30 px square. Below it, centred: a bold title, then one or two lines of the form **`Type:`** description. A box with no product icon (an endpoint, a module) is a smaller, plain box with one line of text, such as `POST /file` or `Module: User Config`.

**Groups.** A rounded-corner rectangle on the surface colour with a bold label at the top-left, and about 40 px of padding around what it holds. A product icon may sit beside the label, as with Cloud Run.

**Datastores** are cylinders, filled in the surface colour, with the product icon at the top-left and a `Store:` line.

**Topics** are ordinary boxes with the Pub/Sub icon and a `Pubsub topic:` line.

## GCP icons

Use the official Google Cloud product icons. The reference image uses these five:

| Service | Used for | Reference box |
| --- | --- | --- |
| Compute Engine (chip) | VMs | Compute Engine, SFTP server |
| Cloud Storage (stacked server) | Buckets | Cloud Storage |
| Pub/Sub (network of dots) | Topics and subscriptions | New File, Confirmation Ready, and the others |
| Cloud Run (double chevron) | The group label of a Cloud Run service | Cloud Run - Serverless |
| Memorystore (chip with a bolt) | Redis and Memcache | Config Cache |

Add other services the same way, using the matching official icon, for example GKE, Cloud SQL, BigQuery, Cloud Functions, Secret Manager or Cloud Scheduler. Put the icon at the top-left. If Lucid has no icon for a service, use a plain box and say so in the key. Never invent an icon.

## Process

1. **Settle the question and the level.** Who reads this and what must they decide or understand? Pick one C4 level.
2. **Gather the elements and relationships from evidence:** the code, the manifests, Terraform, existing pages. Write two tables. Elements: name, type, description, product, group. Relationships: from, to, label. Mark anything unverified.
3. **Show Harry the two tables before you draw** when the diagram is new or large. They are the cheap place to catch mistakes.
4. **Draw it in Lucid** in the house style (see below).
5. **Keep a text twin.** Put the two tables on the page or in the vault beside the link. Neither the Atlassian MCP nor orient can read a Lucid diagram. The twin keeps it readable, searchable and diffable.
6. **Link it.** Add the Lucid link, or the embed, to the Confluence page. Record the document link in the vault note. Name the diagram in the page text.
7. **Check it** against the list below.

## Check before handing over

- One C4 level, with a title that says which.
- Every box has a name, a type and a description. Every arrow has a direction and a label.
- Groups match real boundaries and are labelled top-left.
- External things sit outside the groups.
- Colours match the table, and nothing carries meaning without a key.
- GCP icons are at the top-left of the boxes they describe.
- Unverified items are dashed and labelled `Not confirmed`.
- The text twin matches the diagram.
- No secret, key, internal hostname or customer data is in the diagram.

## Lucid workflow

Verified on 9 Nov 2026 against the `claude.ai Lucid` connector.

1. **Load the tools and read the server's rules first.** Load the tool schemas with ToolSearch. Call `get_mcp_resource` with `lucid://skills/readme` before any other Lucid call, as the server requires. Read `lucid://skills/diagram-specification` before you create a diagram.
2. **Build the JSON with `lucid_style.py`.** It holds the house style as code. `example_carrier_proxy.py` is a full diagram. Place every box yourself. Flow left to right, leave about 90 px between boxes that carry a labelled arrow, and keep at least 35 px of padding inside a group.
3. **Create the document.** Call `lucid_create_diagram_from_specification` with `product` `lucidchart` and `use_assisted_layout` false. Assisted layout moves the boxes and leaves their icons behind.
4. **Set the dark canvas.** The import cannot do it. Run `lucid_run_script` on the new document: `skills.pages.setBackgroundColor(skills.pages.getPagesDetailed()[0].id, '#1f1f21')`. The API sets grid spacing only, not the dot style, so turn the dots on by hand if wanted.
5. **Look at it.** Call `lucid_export_document_as_PNG`. Fix anything wrong: an arrow through a group label, a label over a box, clipped text. Iterate on a new document, because there is no delete tool.
6. **File it.** Final diagrams go in the Lucid folder "Merak research diagrams" (id 454289417). Drafts go in "Scratch (Merak diagram tests)" (id 454289424), renamed `[scratch] ...`. `lucid_update_document` moves and renames.

What works and what does not:

- **GCP icons:** use a `namedShape` with a `GCP2021...Icon` class. They render in the right blues with no styling. Each carries a default label, and only `"text": " "` (one space) removes it. An empty string or a transparent colour does not.
- **Group label:** `containerTitle` sits above the container, not inside it. Use a separate `text` shape at the top-left inside, as the helper does.
- **Preflight:** it reports icon overlaps as errors and padding or label-span rules as warnings. Both are by design here. Fix only structural errors and what the picture shows.
- **Arrows:** elbow and curved arrows get no geometry check, so inspect the PNG.
- **Colour:** set `style.textColor` on boxes. A `text` shape takes colour inline only.
- **Size:** keep a diagram under about 2,600 px wide so it stays readable on a page. A 4,460 px canvas is too wide: wrap the flow into two rows instead.
- **Long titles:** a title longer than about 28 characters on a box with an icon runs into the icon. Shorten it, or widen the box.

Embedding on Confluence:

- **The Lucid macro renders (confirmed by Harry, 9 Nov 2026, after the admin installed the Lucid app on the site).** It is an ADF `extension` node, so a page edit has to go through ADF: `getConfluencePage` with `contentFormat: "adf"`, insert the node, then `updateConfluencePage` with `contentFormat: "adf"`. Script the edit, and re-fetch to check the node count is the old count plus one.
  `{"type":"extension","attrs":{"layout":"default","extensionType":"com.atlassian.confluence.macro.core","extensionKey":"lucidchart","parameters":{"macroParams":{"_parentId":{"value":"<page id>"},"url":{"value":"https://lucid.app/lucidchart/<documentId>/edit"}},"macroMetadata":{"macroId":{"value":"<uuid>"},"schemaVersion":{"value":"1"},"placeholder":[{"type":"image","data":{"url":"https://cdn-cashy-static-assets.lucidchart.com/atlassian/cloud/v1/lucidchart-64x64-reduced-margin.png?url=https%3A%2F%2Flucid.app%2Flucidchart%2F<documentId>%2Fedit&_parentId=<page id>"}}],"title":"Lucidchart Diagrams (atl-embed.lucid.app)"}},"localId":"<uuid>"}}`
- Use the plain `/edit` URL with no `invitationId`. Confluence tends to strip `_parentId` on save (it did on 7 of 8 pages on 9 Nov 2026) and also adds `layout: default` to tables. Both look harmless.
- **The Atlassian MCP drops the macro from markdown.** A markdown update to a page that carries a diagram deletes it. Edit such a page in ADF only, or carry the macro node through unchanged.
- Keep a one-line caption under the macro, `**Diagram:** [<title>](<share link>), in Lucid.`, so people without the Lucid app still have a link. Make the share link with `lucid_create_document_share_link` (role `view`, `restrict_to_account` true, `allow_anonymous` false).
- Smart links also work, if the macro ever fails: an ADF `embedCard`, `inlineCard` or `blockCard` with the Lucid `/view` URL.
- The Atlassian tools cannot delete a page, so a scratch page has to be removed by hand.

## Reference

- `reference/component-diagram.png`: the house style, as a component diagram for the Fuse SFTP connector.
- `lucid_style.py`: the house style as a Python helper that emits Lucid Standard Import JSON.
- `example_carrier_proxy.py`: a complete diagram built with the helper.
- C4 model: https://c4model.com
