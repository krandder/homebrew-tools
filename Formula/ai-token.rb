class AiToken < Formula
  desc "One credential-sync tool for AI CLIs (claude, codex, kimi) via the vault"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/ai-token"
  version "3.1.1"
  sha256 "841b52e895b6c672c22386028001e51d4e7677e638169970bde4ae0356a5598a"

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
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/any-proxy.mjs"
    sha256 "53642288d30724cee06181ecc8d878b1c1d26c13940124e94e4f5b7a8d9de889"
  end

  resource "codex-any-proxy.mjs" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/7f2279643b0c09d34030547de99c4d9d23a62117/codex-any-proxy.mjs"
    sha256 "d45f367a5f51e018355d490a5fbb626de61170e94656af2112863f7e7da7dcea"
  end

  resource "kimi-any-proxy.mjs" do
    url "https://raw.githubusercontent.com/krandder/homebrew-tools/4ba77acf0a3a28a79be86b47c4517ce2fda9ec6e/kimi-any-proxy.mjs"
    sha256 "1abd4c4b376b79fd12c2124eb4aad55bb1ca4486cbe9f73cacb30d3ea70ca8f0"
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
