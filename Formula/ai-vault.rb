class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault"
  version "1.2.0"
  sha256 "ae76f6bb653b43f7bf2c2aeaed0713e05023e38d6a6c9e534b6344c256275760"
  depends_on "codex-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_path_exists bin/"ai-vault"
  end
end
