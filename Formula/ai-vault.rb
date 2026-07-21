class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/5fc1b831e0835ff194d0de0a1e5cacdb64b429dd/ai-vault"
  version "1.3.9"
  sha256 "7c230ac3061c6e03073f31eb378e720da441ab82589788a976baf332c263e0d2"
  depends_on "ai-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_path_exists bin/"ai-vault"
  end
end
