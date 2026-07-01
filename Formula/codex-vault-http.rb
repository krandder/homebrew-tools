class CodexVaultHttp < Formula
  desc "HTTPS front-end for codex-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault-http"
  version "1.2.0"
  sha256 "cab72f333773be71d93492b6378333979c5b978defea9467d64b8ba00bfd1057"

  depends_on "codex-vault"

  def install
    bin.install "codex-vault-http"
  end

  test do
    assert_match "codex-vault-http", shell_output("#{bin}/codex-vault-http --help 2>&1", 1)
  end
end
