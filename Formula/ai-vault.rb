class AiVault < Formula
  desc "Leader-side token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault"
  version "1.2.5"
  sha256 "d358cea427142ea9409cc1ef7e3d81943160e5a3a78d8784eba2cad0fa7ec7eb"
  depends_on "codex-token"
  def install
    bin.install "ai-vault"
  end
  test do
    assert_path_exists bin/"ai-vault"
  end
end
