class CodexVaultHttp < Formula
  desc "HTTPS front-end for codex-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault-http"
  version "1.1.0"
  sha256 "2ce57fa690ad9b708bb50e4092aa42d88b92bd6e988ac73153a8d471eaedc728"

  depends_on "codex-vault"

  def install
    bin.install "codex-vault-http"
  end

  test do
    assert_match "codex-vault-http", shell_output("#{bin}/codex-vault-http --help 2>&1", 1)
  end
end
