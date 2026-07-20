class AiToken < Formula
  desc "One credential-sync tool for AI CLIs (claude, codex, kimi) via the vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-token"
  version "3.0.4"
  sha256 "c37b18ae55e8dd20b4754fa5acf348e6094d5d9776b641be983cf7186d47ade7"

  def install
    bin.install "ai-token"
    # argv0 dispatch: ai-token picks its backend from the shim's basename
    bin.install_symlink bin/"ai-token" => "claude-token"
    bin.install_symlink bin/"ai-token" => "codex-token"
    bin.install_symlink bin/"ai-token" => "kimi-token"
  end

  test do
    assert_match "ai-token 3.0.4", shell_output("#{bin}/ai-token --version")
    assert_match "ai-token 3.0.4", shell_output("#{bin}/claude-token --version")
  end
end
