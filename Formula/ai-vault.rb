class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault"
  version "1.2.4"
  sha256 "1df61a2b82b748465b234fa1cf1c0089ca883f48b586ce2305e929a9c66f4237"
  depends_on "codex-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_path_exists bin/"ai-vault"
  end
end
