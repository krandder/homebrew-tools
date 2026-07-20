class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault"
  version "1.3.6"
  sha256 "9243a323ee8f6abd4e8324591204490ae17dbdcb044efc3a00e8ac7ac98d7c15"
  depends_on "ai-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_path_exists bin/"ai-vault"
  end
end
