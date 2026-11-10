#!/usr/bin/env python3
"""House-style helper for Lucid Standard Import JSON (c4-diagrams skill).

Build a diagram from Python, print Standard Import JSON, pass it to the Lucid MCP
tool `lucid_create_diagram_from_specification` with `use_assisted_layout=false`.
After creating the document, set the dark canvas with `lucid_run_script`:
    skills.pages.setBackgroundColor(skills.pages.getPagesDetailed()[0].id, '#1f1f21')

Standard library only. Colours are sampled from reference/component-diagram.png.

    from lucid_style import Diagram
    d = Diagram()
    g = d.group('g1', 'Cloud Run - Serverless', x=100, y=100, w=700, h=300, icon='CloudRun')
    d.box('a', 'Title', 'Type:', 'Description', x=140, y=160, group=True, icon='PubSub')
    d.edge('a', 'b', 'Label', a_side='bottom', b_side='top')
    print(d.to_json())
"""
import json
import sys

CANVAS = "#1f1f21"
SURFACE = "#303134"      # groups, and boxes outside a group
NESTED = "#242528"       # boxes inside a group
BORDER = "#7e8188"
EDGE = "#75787e"
TEXT = "#cecfd2"

ICONS = {  # GCP 2021 library class names, default size (w, h) from the library
    "ComputeEngine": ("GCP2021ComputeEngineIcon", 128, 113.79),
    "CloudStorage": ("GCP2021CloudStorageIcon", 128, 102),
    "PubSub": ("GCP2021PubsubIcon", 117, 128),
    "CloudRun": ("GCP2021CloudRunIcon", 128, 113.79),
    "Memorystore": ("GCP2021MemorystoreIcon", 128, 128),
    "GKE": ("GCP2021GoogleKubernetesEngineIcon", 113.79, 128),
    "CloudSQL": ("GCP2021CloudSQLIcon", 93.1, 128),
    "CloudFunctions": ("GCP2021CloudFunctionsIcon", 128, 113.79),
    "Dataflow": ("GCP2021DataflowIcon", 96.4, 128),
    "Firestore": ("GCP2021FirestoreIcon", 117, 128),
    "BigQuery": ("GCP2021BigqueryIcon", 128, 128),
    "LoadBalancing": ("GCP2021CloudLoadBalancingIcon", 128, 128),
    "DNS": ("GCP2021CloudDNSIcon", 128, 128),
    "Logging": ("GCP2021CloudLoggingIcon", 128, 128),
    "Monitoring": ("GCP2021CloudMonitoringIcon", 128, 87),
    "PersistentDisk": ("GCP2021PersistentDiskIcon", 102.4, 128),
    "VPC": ("GCP2021VirtualPrivateCloudIcon", 128, 128),
    "KMS": ("GCP2021KeyManagementServiceIcon", 105.7, 128),
    "IAM": ("GCP2021IdentityAndAccessManagementIcon", 105.7, 128),
}

BOX_W, BOX_H = 225, 121
SMALL_W, SMALL_H = 180, 55
ICON_H = 30  # icon height in canvas units; width follows the library aspect ratio


def _stroke(color, width=1, style="solid"):
    return {"color": color, "width": width, "style": style}


def _fill(color):
    return {"type": "color", "color": color}


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Diagram:
    def __init__(self, page_id="p1", title="Diagram"):
        self.page_id, self.title = page_id, title
        self.shapes, self.lines = [], []
        self._ids = set()
        self._box = {}  # id -> (x, y, w, h)

    def _add(self, shape):
        assert shape["id"] not in self._ids, "duplicate id " + shape["id"]
        self._ids.add(shape["id"])
        self.shapes.append(shape)

    def icon(self, shape_id, kind, x, y, h=ICON_H):
        cls, w0, h0 = ICONS[kind]
        w = round(h * w0 / h0, 1)
        # text ' ' (one space) is what suppresses the library's default label
        self._add({"id": shape_id, "type": "namedShape", "className": cls,
                   "boundingBox": {"x": x, "y": y, "w": w, "h": h}, "text": " "})

    def group(self, shape_id, label, x, y, w, h, icon=None, label_w=320):
        """A boundary. Draw groups BEFORE the boxes they hold (z-order)."""
        self._add({"id": shape_id, "type": "rectangleContainer",
                   "boundingBox": {"x": x, "y": y, "w": w, "h": h},
                   "style": {"fill": _fill(SURFACE), "stroke": _stroke(BORDER)}})
        lx = x + 12
        if icon:
            self.icon(shape_id + "_icon", icon, x + 10, y + 8)
            lx = x + 10 + round(ICON_H * ICONS[icon][1] / ICONS[icon][2]) + 8
        self._add({"id": shape_id + "_label", "type": "text",
                   "boundingBox": {"x": lx, "y": y + 11, "w": min(w - (lx - x) - 10, label_w), "h": 22},
                   "text": '<p style="font-size:12px;color:%s"><b>%s</b></p>' % (TEXT, _esc(label))})
        self._box[shape_id] = (x, y, w, h)

    def box(self, shape_id, title, type_label, desc, x, y, w=BOX_W, h=BOX_H,
            nested=False, icon=None, dashed=False):
        """A component box. nested=True when it sits inside a group (darker fill)."""
        body = '<b>%s</b><br><b>%s</b> %s' % (_esc(title), _esc(type_label), _esc(desc)) if type_label \
            else '<b>%s</b><br>%s' % (_esc(title), _esc(desc))
        self._add({"id": shape_id, "type": "rectangle",
                   "boundingBox": {"x": x, "y": y, "w": w, "h": h},
                   "text": '<p style="font-size:12px;text-align:center">%s</p>' % body,
                   "style": {"fill": _fill(NESTED if nested else SURFACE),
                             "stroke": _stroke("#1f1f21" if nested else BORDER, 1,
                                               "dashed" if dashed else "solid"),
                             "textColor": TEXT}})
        if icon:
            self.icon(shape_id + "_icon", icon, x + 7, y + 7)
        self._box[shape_id] = (x, y, w, h)

    def note(self, shape_id, html, x, y, w, h):
        """Free text (a note under a diagram). html may use <br> and <b>."""
        self._add({"id": shape_id, "type": "text", "boundingBox": {"x": x, "y": y, "w": w, "h": h},
                   "text": '<p style="font-size:11px;color:%s;text-align:left">%s</p>' % (TEXT, html)})

    def small(self, shape_id, text, x, y, w=SMALL_W, h=SMALL_H, nested=True):
        """A plain one-line box for endpoints and modules. Use <b>Type:</b> in text if wanted."""
        self._add({"id": shape_id, "type": "rectangle",
                   "boundingBox": {"x": x, "y": y, "w": w, "h": h},
                   "text": '<p style="font-size:12px;text-align:center">%s</p>' % text,
                   "style": {"fill": _fill(NESTED if nested else SURFACE),
                             "stroke": _stroke("#1f1f21" if nested else BORDER),
                             "textColor": TEXT}})
        self._box[shape_id] = (x, y, w, h)

    def datastore(self, shape_id, title, type_label, desc, x, y, w=207, h=112, icon=None, dashed=False):
        """A cylinder. Standalone (surface fill), border like a boundary."""
        self._add({"id": shape_id, "type": "database",
                   "boundingBox": {"x": x, "y": y, "w": w, "h": h},
                   "text": '<p style="font-size:12px;text-align:center"><b>%s</b><br><b>%s</b> %s</p>'
                           % (_esc(title), _esc(type_label), _esc(desc)),
                   "style": {"fill": _fill(SURFACE), "stroke": _stroke(BORDER, 1, "dashed" if dashed else "solid"),
                             "textColor": TEXT}})
        if icon:
            self.icon(shape_id + "_icon", icon, x + 12, y + 16)
        self._box[shape_id] = (x, y, w, h)

    @staticmethod
    def _pos(side):
        return {"top": (0.5, 0), "bottom": (0.5, 1), "left": (0, 0.5), "right": (1, 0.5)}[side]

    def edge(self, a, b, label=None, a_side="right", b_side="left", kind="elbow",
             both=False, dashed=False, label_pos=0.5, a_pos=None, b_pos=None):
        """One arrow from a to b. kind: straight | elbow | curved. dashed = 'Not confirmed'."""
        assert a in self._box and b in self._box, "unknown endpoint"
        ax, ay = a_pos if a_pos else self._pos(a_side)  # a_pos/b_pos: exact (x, y) in 0..1 on the box
        bx, by = b_pos if b_pos else self._pos(b_side)
        line = {"id": "e%d" % (len(self.lines) + 1), "lineType": kind,
                "endpoint1": {"type": "shapeEndpoint", "style": "openArrow" if both else "none",
                              "shapeId": a, "position": {"x": ax, "y": ay}},
                "endpoint2": {"type": "shapeEndpoint", "style": "openArrow",
                              "shapeId": b, "position": {"x": bx, "y": by}},
                "stroke": _stroke(EDGE, 1, "dashed" if dashed else "solid")}
        if label:
            line["text"] = [{"text": '<span style="font-size:9px;color:%s">%s</span>' % (TEXT, _esc(label)),
                             "position": label_pos, "side": "top"}]
        self.lines.append(line)

    def title_block(self, text, x, y, w=520):
        """A diagram title in the top-left, outside every group."""
        self._add({"id": "title", "type": "text", "boundingBox": {"x": x, "y": y, "w": w, "h": 28},
                   "text": '<p style="font-size:16px;color:%s"><b>%s</b></p>' % (TEXT, _esc(text))})

    def key_block(self, x, y, rows):
        """A small key. rows = list of (label, color). Drawn as coloured swatches and text."""
        for i, (label, color) in enumerate(rows):
            self._add({"id": "key_sw%d" % i, "type": "rectangle",
                       "boundingBox": {"x": x, "y": y + i * 26, "w": 22, "h": 14},
                       "style": {"fill": _fill(color), "stroke": _stroke(BORDER)}})
            self._add({"id": "key_tx%d" % i, "type": "text",
                       "boundingBox": {"x": x + 30, "y": y + i * 26 - 4, "w": 260, "h": 22},
                       "text": '<p style="font-size:11px;color:%s">%s</p>' % (TEXT, _esc(label))})

    def to_dict(self):
        return {"version": 1, "pages": [{"id": self.page_id, "title": self.title,
                                         "shapes": self.shapes, "lines": self.lines}]}

    def to_json(self, indent=None):
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=True)


if __name__ == "__main__":
    d = Diagram(title="Self test")
    d.group("g", "Cloud Run - Serverless", 100, 100, 480, 220, icon="CloudRun")
    d.small("a", "POST /file", 140, 170)
    d.small("b", "<b>Module:</b> User Config", 360, 170)
    d.edge("a", "b", "Lookup user")
    sys.stdout.write(d.to_json() + "\n")
