class CodexVaultHttp < Formula
  desc "HTTPS front-end for codex-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault-http"
  version "1.1.0"
  sha256 "8c7aa1fad7f13ca57fd03d87033cd4dc10d06c4a33bb9ced67dc5eec316fb83b"

  depends_on "codex-vault"

  def install
    bin.install "codex-vault-http"
  end

  test do
    assert_match "codex-vault-http", shell_output("#{bin}/codex-vault-http --help 2>&1", 1)
  end
end
