class AiVaultHttp < Formula
  desc "HTTPS front-end for ai-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/371ddda3fcc26930c58910208929fc5ab94a6979/ai-vault-http"
  version "1.2.7"
  sha256 "dc836a0f73ea98927451dc0252d30cef32f919a0c382bbe74befaefef939f73d"
  depends_on "ai-vault"
  def install
    bin.install "ai-vault-http"
  end
  test do
    assert_path_exists bin/"ai-vault-http"
  end
end
