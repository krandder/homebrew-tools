class CodexVaultHttp < Formula
  desc "HTTPS front-end for codex-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault-http"
  version "1.0.0"
  sha256 "5effb7188fee653a6a586e746e399ecdfa668b9981b79708aba77243a59eb000"

  depends_on "codex-vault"

  def install
    bin.install "codex-vault-http"
  end

  test do
    assert_match "codex-vault-http", shell_output("#{bin}/codex-vault-http --help 2>&1", 1)
  end
end
