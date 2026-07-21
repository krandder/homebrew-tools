class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/85fd87ad1479b1b29bf7ada8bdfaaeb590fab032/ai-vault"
  version "1.3.8"
  sha256 "9a132dc3df7679d23350d92428a6608e4e989ddbc5362021ccb2b9b63a7e7358"
  depends_on "ai-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_path_exists bin/"ai-vault"
  end
end
