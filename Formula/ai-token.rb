class AiToken < Formula
  desc "One credential-sync tool for AI CLIs (claude, codex, kimi) via the vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-token"
  version "3.0.1"
  sha256 "331315fd8b903df8c81ab95f903a2af8e267f01d3ee317ef5db648bd858c81b8"

  def install
    bin.install "ai-token"
    # argv0 dispatch: ai-token picks its backend from the shim's basename
    bin.install_symlink bin/"ai-token" => "claude-token"
    bin.install_symlink bin/"ai-token" => "codex-token"
    bin.install_symlink bin/"ai-token" => "kimi-token"
  end

  test do
    assert_match "ai-token 3.0.1", shell_output("#{bin}/ai-token --version")
    assert_match "ai-token 3.0.1", shell_output("#{bin}/claude-token --version")
  end
end
