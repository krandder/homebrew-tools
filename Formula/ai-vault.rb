class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/ff5ee71c54b4f442b9071dc19ddf7124a2ad345b/ai-vault"
  version "1.3.7"
  sha256 "1dc2148c4372e6bf4d7e653064ed23fff79306652cb971779113dd0e07e7457c"
  depends_on "ai-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_path_exists bin/"ai-vault"
  end
end
