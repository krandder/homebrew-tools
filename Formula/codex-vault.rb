class CodexVault < Formula
  desc "Leader-side Codex token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault"
  version "1.0.0"
  sha256 "e32c612b07ec3f2948868dba37894330fd9c6016adab58f2e51ed408c383bcaa"

  depends_on "codex-token"

  def install
    bin.install "codex-vault"
  end

  test do
    assert_match "codex-vault", shell_output("#{bin}/codex-vault --help 2>&1", 1)
  end
end
