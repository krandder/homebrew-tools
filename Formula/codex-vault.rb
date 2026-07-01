class CodexVault < Formula
  desc "Leader-side Codex token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault"
  version "1.3.0"
  sha256 "fbc1430618bd49a497d2e3c271d5081bca741e511143c80b9907a5abb694bc3d"

  depends_on "codex-token"

  def install
    bin.install "codex-vault"
  end

  test do
    assert_match "codex-vault", shell_output("#{bin}/codex-vault --help 2>&1", 1)
  end
end
