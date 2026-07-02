class ClaudeBroker < Formula
  desc "Install/run the transparent Claude OAuth refresh broker on a follower"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-broker"
  version "1.3.0"
  sha256 "2dbedb1d4fa74e3cfe2f080bfc99f78f3237464db9b381081e0244340e21de62"
  depends_on "claude-broker-proxy"
  def install
    bin.install "claude-broker"
  end
  test do
    assert_predicate bin/"claude-broker", :exist?
  end
end
