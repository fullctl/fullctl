// UI controller for the security-keys / passkey management table:
// register a new key, toggle a key's passkey-login mode, remove a key.
// All three actions POST to the django-security-keys JSON endpoints
// after running the appropriate WebAuthn ceremony.

account.SecurityKeysManager = twentyc.cls.define(
  "SecurityKeysManager",
  {
    SecurityKeysManager: function() {
      this.config = document.getElementById("securitykeys-config");
      if (!this.config) return;

      // Set the global SecurityKeys.config that request_registration() and
      // request_authenticate() read from. We assign directly instead of
      // calling SecurityKeys.init() because init() also wires the bundled
      // register-form handler, which calls request_registration() without
      // passing a password and breaks server-side password verification.
      SecurityKeys.config = {
        url_request_registration: this.config.dataset.urlRequestRegistration,
        url_request_authentication: this.config.dataset.urlRequestAuthentication,
        csrf_token: this.config.dataset.csrfToken,
      };

      this.wireRegister();
      this.wireRemove();
      this.wireToggle();
    },

    // Generate a unique fallback name for a new key when the user leaves
    // the name field blank. Picks "security-key", "security-key 2",
    // "security-key 3", … skipping any names already taken.
    nextDefaultName: function() {
      var existing = [];
      document.querySelectorAll(".js-securitykey-remove").forEach(function(btn) {
        existing.push(btn.dataset.keyName);
      });
      if (existing.indexOf("security-key") === -1) return "security-key";
      var n = 2;
      while (existing.indexOf("security-key " + n) !== -1) n++;
      return "security-key " + n;
    },

    showError: function(msg) {
      var el = document.getElementById("errors-alert");
      el.innerHTML = '<div class="alert alert-danger"></div>';
      el.firstChild.textContent = msg;
    },

    post: function(url, data) {
      var body = new FormData();
      Object.keys(data).forEach(function(k) {
        if (data[k] !== undefined && data[k] !== null) body.append(k, data[k]);
      });
      return fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": this.config.dataset.csrfToken },
        body: body,
      });
    },

    // Register a new key: read inputs from the register row, run the
    // WebAuthn registration ceremony (which validates the password
    // server-side first), then POST the resulting credential.
    wireRegister: function() {
      var self = this;
      var btn = document.getElementById("register-key-button");
      if (!btn) return;
      var row = document.getElementById("register-key-row");

      btn.addEventListener("click", function() {
        var password = row.querySelector('input[name="password"]').value;
        var name = row.querySelector('input[name="name"]').value || self.nextDefaultName();
        var passkeyLogin = row.querySelector('input[name="passkey_login"]').checked;

        if (!password) {
          self.showError("Please enter your current password to add a security key.");
          return;
        }

        btn.disabled = true;
        SecurityKeys.request_registration(
          password,
          function(credentialJson) {
            self.post(self.config.dataset.urlRegister, {
              password: password,
              name: name,
              credential: credentialJson,
              passkey_login: passkeyLogin ? "true" : null,
            }).then(function(resp) {
              if (resp.ok) {
                window.location.reload();
              } else {
                btn.disabled = false;
                resp.json().catch(function() { return {}; }).then(function(data) {
                  self.showError(
                    (data.non_field_errors && data.non_field_errors[0])
                    || "Failed to register security key."
                  );
                });
              }
            });
          },
          function(exc) {
            btn.disabled = false;
            self.showError((exc && exc.message) || "Security key registration failed.");
          }
        );
      });
    },

    // Remove a key: confirm, then run a WebAuthn assertion ceremony to
    // re-verify the user. The decommission endpoint refuses to delete
    // unless the request includes either a fresh assertion or a TOTP
    // token, so the ceremony is mandatory — not just defense-in-depth.
    wireRemove: function() {
      var self = this;
      document.querySelectorAll(".js-securitykey-remove").forEach(function(btn) {
        btn.addEventListener("click", function() {
          if (!window.confirm("Remove " + btn.dataset.keyName + "?")) return;

          btn.disabled = true;
          SecurityKeys.request_authenticate(
            "",     // username — server uses the current session
            false,  // for_login=false → 2FA verification, not a login attempt
            function(payload) {
              self.post(self.config.dataset.urlDecommission, {
                id: btn.dataset.keyId,
                credential: payload.credential,
              }).then(function(resp) {
                if (resp.ok) {
                  window.location.reload();
                } else {
                  btn.disabled = false;
                  self.showError("Failed to remove security key.");
                }
              });
            },
            function() {
              btn.disabled = false;
              self.showError("No security key credentials available.");
            },
            function(exc) {
              btn.disabled = false;
              self.showError((exc && exc.message) || "Security key authentication failed.");
            },
            true  // ignore_credential_filter — any of the user's keys can re-auth
          );
        });
      });
    },

    // Flip a key's passkey-login mode (allow login ↔ 2nd-factor only).
    // No WebAuthn ceremony needed; the endpoint only updates the flag.
    wireToggle: function() {
      var self = this;
      document.querySelectorAll(".js-securitykey-toggle").forEach(function(btn) {
        btn.addEventListener("click", function() {
          btn.disabled = true;
          self.post(self.config.dataset.urlUpdate, {
            id: btn.dataset.keyId,
            passkey_login: btn.dataset.targetMode,
          }).then(function(resp) {
            if (resp.ok) {
              window.location.reload();
            } else {
              btn.disabled = false;
              self.showError("Failed to update key mode.");
            }
          });
        });
      });
    }
  }
);

// Backup-tokens regen page: wire the "Confirm with security key" button.
// The page also accepts a TOTP/backup code through the form; this class only
// drives the WebAuthn path. The form's `credential` hidden field is populated
// from a successful assertion and the form is auto-submitted.
account.BackupTokensReauth = twentyc.cls.define(
  "BackupTokensReauth",
  {
    BackupTokensReauth: function() {
      this.config = document.getElementById("backup-tokens-securitykey-config");
      if (!this.config) return;

      this.form = document.getElementById("backup-tokens-form");
      this.button = document.getElementById("backup-tokens-securitykey-btn");
      this.errors = document.getElementById("errors-alert");
      if (!this.form || !this.button) return;

      SecurityKeys.config = {
        url_request_authentication: this.config.dataset.urlRequestAuthentication,
        csrf_token: this.config.dataset.csrfToken,
      };

      var self = this;
      this.button.addEventListener("click", function() { self.confirm(); });
    },

    showError: function(msg) {
      if (!this.errors) return;
      this.errors.innerHTML = '<div class="alert alert-danger"></div>';
      this.errors.firstChild.textContent = msg;
    },

    // Drive the WebAuthn assertion ceremony, drop the credential into the
    // form's hidden field, and submit. DisableForm.clean() verifies the
    // assertion server-side via SecurityKey.verify_authentication.
    confirm: function() {
      var self = this;
      self.button.disabled = true;
      SecurityKeys.request_authenticate(
        "",     // username — server uses the current session
        false,  // for_login=false -> 2FA verification, not a login attempt
        function(payload) {
          self.form.querySelector('input[name="credential"]').value = payload.credential;
          self.form.submit();
        },
        function() {
          self.button.disabled = false;
          self.showError(gettext("No security key credentials available."));
        },
        function(exc) {
          self.button.disabled = false;
          self.showError((exc && exc.message) || gettext("Security key authentication failed."));
        },
        true  // ignore_credential_filter — any of the user's keys can re-auth
      );
    }
  }
);

$(document).ready(function() {
  new account.SecurityKeysManager();
  new account.BackupTokensReauth();
});
