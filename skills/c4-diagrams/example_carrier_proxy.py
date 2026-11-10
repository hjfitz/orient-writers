import sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from lucid_style import Diagram
d = Diagram(title="Component diagram: a carrier proxy")
d.title_block("Component diagram: a carrier proxy, when Selector asks for a label", 60, 12, 700)
W, H = 210, 120
X1, X2, X3 = 415, 720, 1025            # columns inside the group, 95 px gaps
# outside the group
d.box("E2", "ApiKy", "System:", "Checks the key and returns the customer profile", 470, 55, w=200, h=105)
d.datastore("E9", "Customer credentials", "Store:", "MongoDB, per customer", 740, 50, w=207, h=112)
d.datastore("E10", "Shared GFS account", "Store:", "One account for all customers. Not confirmed", 1030, 50, w=207, h=112, dashed=True)
d.box("E1", "Selector site", "System:", "CSS or Client4 at a customer site", 60, 265, h=120)
d.box("E11", "Carrier API", "System:", "REST, plus an OAuth token endpoint. UPS also takes XML", 1430, 265, h=120)
# the proxy
d.group("G", "Carrier proxy", 380, 200, 890, 420, icon="GKE")
d.box("E3", "Request handler", "Node.js:", "Reads x-api-key and asks ApiKy who the customer is", X1, 265, w=W, h=H, nested=True)
d.box("E4", "Credentials lookup", "Node.js:", "Turns the customer profile into a carrier account", X2, 265, w=W, h=H, nested=True)
d.box("E5", "Carrier token handler", "OAuth:", "Gets and caches the carrier's token, where one is used", X3, 265, w=W, h=H, nested=True)
d.box("E6", "Request mapper", "Node.js:", "Maps Selector's request to the carrier's format", X3, 450, w=W, h=H, nested=True)
d.box("E7", "Carrier client", "HTTPS:", "Calls the carrier's REST or XML API", X2, 450, w=W, h=H, nested=True)
d.box("E8", "Response mapper", "Node.js:", "Builds a label, tracking numbers and errors", X1, 450, w=W, h=H, nested=True)
# edges
d.edge("E1", "E3", "Label request and key", "right", "left", kind="straight")
d.edge("E3", "E2", "Check key, get profile", "top", "bottom", kind="straight", a_pos=(0.75, 0), b_pos=(0.5, 1))
d.edge("E3", "E4", "Customer profile", "right", "left", kind="straight")
d.edge("E4", "E9", "Customer's credentials", "top", "bottom", kind="straight", a_pos=(0.45, 0), b_pos=(0.5, 1))
d.edge("E4", "E10", "Shared account, if none", "top", "bottom", dashed=True, a_pos=(0.85, 0), b_pos=(0.2, 1), label_pos=0.6)
d.edge("E4", "E5", "Credentials", "right", "left", kind="straight")
d.edge("E5", "E11", "Request token", "right", "left", kind="straight")
d.edge("E5", "E6", "Credentials and token", "bottom", "top", kind="straight")
d.edge("E6", "E7", "Mapped request", "left", "right", kind="straight")
d.edge("E7", "E8", "Carrier reply", "left", "right", kind="straight")
d.edge("E7", "E11", "Create the label", "bottom", "bottom", label_pos=0.72)
d.edge("E8", "E1", "Label, tracking numbers, errors", "left", "bottom", label_pos=0.6)
d.note("N1", "<b>Hosting.</b> GKE workload for most proxies. Cloud Run for FedEx and InPost.<br><b>Credential pattern by proxy.</b> MongoDB, per customer: Royal Mail, FedEx, InPost, Exelot, DPD Europe. ApiKy profile: BJS. One GFS account: UPS, OCS, Coll8. Not checked: Amazon.", 60, 690, 900, 50)
d.note("N2", "<b>Key.</b> Dashed box or arrow: not confirmed. Cylinder: a datastore. Arrows follow the request. Replies on the same call are not drawn.", 60, 760, 900, 30)
open("/tmp/proxy.json", "w").write(d.to_json())
print(len(d.shapes), "shapes", len(d.lines), "lines")
