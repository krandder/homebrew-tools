class CodexToken < Formula
  desc "Extract OpenAI Codex CLI authentication credentials"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/codex-token"
  version "1.0.0"
  sha256 "38ca3c6abecf1998784c42f2d251fae7d57541cc32cc62c33c66be98999cb337"

  def install
    bin.install "codex-token"
  end

  test do
    assert_predicate bin/"codex-token", :exist?
  end
end
