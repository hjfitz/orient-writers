import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config_snapshot as cs

SFTP = {"connectorId": "conn_a", "storefrontId": "sf_a", "businessId": "B", "friendlyName": "Main SFTP",
        "confirmationsEnabled": True,
        "config": {"type": "sftp", "isActive": "true", "host": "sftp.example", "stockAdjustmentsEnabled": False,
                   "auth": {"mode": "key", "privateKey": "-----BEGIN PRIVATE KEY-----abcdef", "publicKey": "ssh-rsa AAAApublic"},
                   "user": {"username": "someuser"}},
        "sales_order": {"useCase": "sales_order", "status": "active",
                        "config": {"rules": {"header": [{"from": "a", "to": "b"}], "lines": [{"from": "c", "to": "d"}]},
                                   "defaults": {"header": [{"key": "carrierId", "value": "OWN"}]}}},
        "master_data": None}
API = {"connectorId": "conn_b", "businessId": "B", "friendlyName": "API",
       "config": {"type": "rest", "apiKey": "sk_live_supersecret", "webhookSecretKey": "whsec_topsecret",  # gitleaks:allow synthetic fixture for the redaction test
                  "webhookUrl": "https://hooks.example.com/path?token=zzz"}}
BACKEND = {"config": {"businessId": "B", "type": "snap", "host": "https://snap.example",
                      "credentials": {"username": "u", "password": "hunter2hunter2"}, "broadcastConfirmations": True}}


class Projection(unittest.TestCase):
    def test_connector_drops_every_secret_value(self):
        raw = [SFTP, API, BACKEND]
        projected = [cs.project_connector({}, SFTP), cs.project_connector({}, API), cs.project_backend(BACKEND)]
        cs.assert_no_secrets(projected, cs.secret_values(raw))

    def test_guard_refuses_a_leaked_secret(self):
        with self.assertRaises(RuntimeError):
            cs.assert_no_secrets({"x": "hunter2hunter2"}, {"hunter2hunter2"})

    def test_mapping_defaults_key_names_are_not_treated_as_secrets(self):
        self.assertNotIn("carrierId", cs.secret_values(SFTP))

    def test_webhook_url_keeps_only_its_host(self):
        self.assertEqual(cs.project_connector({}, API)["webhookHost"], "hooks.example.com")

    def test_use_cases_carry_a_hash_not_the_mapping(self):
        uc = cs.project_connector({}, SFTP)["useCases"]["sales_order"]
        self.assertEqual((uc["rules"], len(uc["mapping"])), (2, 12))

    def test_unmapped_use_cases_are_omitted(self):
        self.assertNotIn("master_data", cs.project_connector({}, SFTP)["useCases"])


class Report(unittest.TestCase):
    def snaps(self, prod=True):
        return {"B": {"environments": {"prod": {}} if prod else {"dev": {}}}}

    def test_baseline_run_says_there_is_nothing_to_compare(self):
        out = cs.render_report({"B": []}, self.snaps(), {}, set())
        self.assertIn("baseline run", out)

    def test_prod_change_is_tabulated_with_its_business(self):
        fresh = {"B": [{"at": "2026-10-13", "env": "prod", "subject": "Main SFTP", "summary": "confirmationsEnabled: True -> False"}]}
        out = cs.render_report(fresh, self.snaps(), {"B": {"synced": "2026-10-12T07:00Z"}}, set())
        self.assertIn("| Main SFTP | confirmationsEnabled: True -> False |", out)

    def test_change_to_a_narrated_business_flags_the_narrative(self):
        fresh = {"B": [{"at": "d", "env": "prod", "subject": "x", "summary": "y"}]}
        out = cs.render_report(fresh, self.snaps(), {"B": {"synced": "t"}}, {"B"})
        self.assertIn("Narrative may be stale", out)

    def test_dev_changes_are_counted_not_listed(self):
        fresh = {"B": [{"at": "d", "env": "dev", "subject": "x", "summary": "y"}]}
        out = cs.render_report(fresh, self.snaps(), {"B": {"synced": "t"}}, set())
        self.assertNotIn("| x | y |", out)


class Yaml(unittest.TestCase):
    def test_mapping_hash_is_never_a_yaml_number(self):
        import yaml
        for value in ({"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}, {"a": 5}):
            self.assertIsInstance(yaml.safe_load("m: %s" % cs._short_hash(value))["m"], str)


class Diff(unittest.TestCase):
    def block(self, **over):
        c = cs.project_connector({}, SFTP); c.update(over)
        return {"storefronts": [], "connectors": [c]}

    def test_first_sight_is_a_baseline_not_a_change(self):
        self.assertEqual(cs.diff_environment("prod", None, self.block(), "2026-10-13"), [])

    def test_flag_flip_is_reported_with_both_values(self):
        out = cs.diff_environment("prod", self.block(), self.block(confirmationsEnabled=False), "2026-10-13")
        self.assertEqual(out[0]["summary"], "confirmationsEnabled: True -> False")

    def test_removed_connector_is_reported(self):
        out = cs.diff_environment("prod", self.block(), {"storefronts": [], "connectors": []}, "2026-10-13")
        self.assertEqual(out[0]["summary"], "connector removed")


if __name__ == "__main__":
    unittest.main()
