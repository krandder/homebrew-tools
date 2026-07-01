class CodexVault < Formula
  desc "Leader-side Codex token vault: owner-gated push, ACL-gated pull, audit"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-vault"
  version "1.2.0"
  sha256 "a708d92da30ef33ad6756dfd0530d93b5db12895b97f986464008adf843a4c2f"

  depends_on "codex-token"

  def install
    bin.install "codex-vault"
  end

  test do
    assert_match "codex-vault", shell_output("#{bin}/codex-vault --help 2>&1", 1)
  end
end
