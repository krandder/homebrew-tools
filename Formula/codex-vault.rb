class CodexVault < Formula
  desc "Leader-side Codex token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault"
  version "1.1.0"
  sha256 "ecdf256fcc31f75ee1c9ab22cb844407de5d0333836f21e347aea75e6b9024da"

  depends_on "codex-token"

  def install
    bin.install "codex-vault"
  end

  test do
    assert_match "codex-vault", shell_output("#{bin}/codex-vault --help 2>&1", 1)
  end
end
