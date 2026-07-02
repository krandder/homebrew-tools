class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault"
  version "1.1.0"
  sha256 "f7edce17de3692628f4f4e541ea3e24d9990759b9ed99867834ab5addf3e4609"
  depends_on "codex-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_predicate bin/"ai-vault", :exist?
  end
end
