class AiToken < Formula
  desc "One credential-sync tool for AI CLIs (claude, codex, kimi) via the vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/ai-token"
  version "3.1.3"
  sha256 "342e23b09f76a1f5d441f03140af54ac853496b40d3a26c513ebd75dc35dc601"

  # The whole formula installs from the same immutable merge commit so all
  # files are guaranteed to be available together.
  resource "claude-any" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/claude-any"
    sha256 "03c3970c863b4174ccfb9adb396eab6360237b611927f631c811bf9feff17a65"
  end

  resource "codex-any" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/codex-any"
    sha256 "a47ccce9d01d803f5842f67b3a223af8495082baad859e12f0da523c7f188c5e"
  end

  resource "kimi-any" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/4ba77acf0a3a28a79be86b47c4517ce2fda9ec6e/kimi-any"
    sha256 "69fcc3dfaf56be656658fef1463d1e06f808f5777dca05a6c05e174244de78b8"
  end

  resource "claude-any-mirror" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/claude-any-mirror"
    sha256 "b5b0453b4c403fd4d4ba5ac84270c361bb660486c3afb381b987f207a88368a0"
  end

  resource "codex-any-mirror" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/codex-any-mirror"
    sha256 "fc48644309a5cf05d979d1b0a03b418ab914a2e89621964405bcf295ff925e4c"
  end

  resource "kimi-any-mirror" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/4ba77acf0a3a28a79be86b47c4517ce2fda9ec6e/kimi-any-mirror"
    sha256 "ade12fdee0278712cb357922fdbe016fe00d3fcd267b646291f539d609e8b42b"
  end

  resource "imgpush" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/imgpush"
    sha256 "53e642c3bf891f0121f789a0c0b7848e9740b1fe3ddeb3a5dd32d0f3159345e9"
  end

  resource "kimg" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/kimg"
    sha256 "f19acf1c057a7e080b3f2ee7b2a9249bb799ab3d885436fa4a249e1949f523de"
  end

  resource "farol-connect" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/farol-connect"
    sha256 "9d7c3866a725c0fffe001507af863b240b66dcbfc19b1a0c41999342415266b6"
  end

  resource "any-proxy.mjs" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/d79f8ccf9d32123d90ac46f1daee8af356954f13/any-proxy.mjs"
    sha256 "6d03e8225c9ed062665be18ba31dc045c1692ed958b510c0debdd09a3020ece0"
  end

  resource "codex-any-proxy.mjs" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/b3cb8cc01b517e4d2bb5f6b1a7f35345a868bdd3/codex-any-proxy.mjs"
    sha256 "e911db57ab69e22ad5494c542bafb36a1c99c1fcf5717d50a5d13f1d59166a6f"
  end

  resource "kimi-any-proxy.mjs" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/d79f8ccf9d32123d90ac46f1daee8af356954f13/kimi-any-proxy.mjs"
    sha256 "d7d63ad40aee6e352557cdee962fe8f5f8d129e3fc863f5f8b73daaec648cb83"
  end

  def install
    bin.install "ai-token"
    # argv0 dispatch: ai-token picks its backend from the shim's basename
    bin.install_symlink bin/"ai-token" => "claude-token"
    bin.install_symlink bin/"ai-token" => "codex-token"
    bin.install_symlink bin/"ai-token" => "kimi-token"

    # -any failover stack: CLI wrappers, follower mirrors, and helpers
    %w[
      claude-any codex-any kimi-any
      claude-any-mirror codex-any-mirror kimi-any-mirror
      imgpush kimg farol-connect
    ].each { |tool| bin.install resource(tool) }

    # The proxies are long-running user services (node >= 18 or bun), not
    # one-shot bin commands, so they live under share.
    (share/"any-proxies").install resource("any-proxy.mjs"),
                                 resource("codex-any-proxy.mjs"),
                                 resource("kimi-any-proxy.mjs")
  end

  def caveats
    <<~EOS
      The -any failover proxies were installed to:
        #{opt_share}/any-proxies
      They need node >= 18 or bun and run as systemd user services (Linux) or
      launchd agents (macOS) on 127.0.0.1: any-proxy.mjs port 7800,
      codex-any-proxy.mjs port 7810, kimi-any-proxy.mjs port 7812.
    EOS
  end

  test do
    assert_match(/^ai-token \d+\.\d+\.\d+$/, shell_output("#{bin}/ai-token --version").strip)
    assert_match(/^claude-token \d+\.\d+\.\d+$/, shell_output("#{bin}/claude-token --version").strip)
    %w[
      claude-any codex-any kimi-any
      claude-any-mirror codex-any-mirror kimi-any-mirror
      imgpush kimg farol-connect
    ].each do |tool|
      assert_predicate bin/tool, :executable?
    end
    %w[any-proxy.mjs codex-any-proxy.mjs kimi-any-proxy.mjs].each do |proxy|
      assert_predicate share/"any-proxies"/proxy, :exist?
    end
  end
end
