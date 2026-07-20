class AiToken < Formula
  desc "One credential-sync tool for AI CLIs (claude, codex, kimi) via the vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-token"
  version "3.0.3"
  sha256 "274163069d692219307f78538c45630a487419b76166571f57eaf59904e1bdd9"

  def install
    bin.install "ai-token"
    # argv0 dispatch: ai-token picks its backend from the shim's basename
    bin.install_symlink bin/"ai-token" => "claude-token"
    bin.install_symlink bin/"ai-token" => "codex-token"
    bin.install_symlink bin/"ai-token" => "kimi-token"
  end

  test do
    assert_match "ai-token 3.0.3", shell_output("#{bin}/ai-token --version")
    assert_match "ai-token 3.0.3", shell_output("#{bin}/claude-token --version")
  end
end
