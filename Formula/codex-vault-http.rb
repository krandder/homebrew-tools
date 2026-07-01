class CodexVaultHttp < Formula
  desc "HTTPS front-end for codex-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault-http"
  version "1.3.0"
  sha256 "dcf8643d3481866d64468d67e39b620f7cb96a386237a4d023c2e19d8f1827f6"

  depends_on "codex-vault"

  def install
    bin.install "codex-vault-http"
  end

  test do
    assert_match "codex-vault-http", shell_output("#{bin}/codex-vault-http --help 2>&1", 1)
  end
end
