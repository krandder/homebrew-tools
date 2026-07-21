class AiVaultHttp < Formula
  desc "HTTPS front-end for ai-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/5fc1b831e0835ff194d0de0a1e5cacdb64b429dd/ai-vault-http"
  version "1.2.6"
  sha256 "a616d6a1b7fe11a69cda70f728bf11faf642159eca9fc6900bb3a9e4b20bf0fa"
  depends_on "ai-vault"
  def install
    bin.install "ai-vault-http"
  end
  test do
    assert_path_exists bin/"ai-vault-http"
  end
end
