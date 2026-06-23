class CodexVault < Formula
  desc "Leader-side Codex token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault"
  version "1.0.0"
  sha256 "85153fc92d9b362c04f0705a0ea07baf6b78768f78f664f6e70f47bc824fc413"

  depends_on "codex-token"

  def install
    bin.install "codex-vault"
  end

  test do
    assert_match "codex-vault", shell_output("#{bin}/codex-vault --help 2>&1", 1)
  end
end
