include $(TOPDIR)/rules.mk

PKG_NAME:=ex511-v2-factory
PKG_VERSION:=1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/ex511-v2-factory
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=EX511 v2 factory radio data validation
  DEPENDS:=@TARGET_qualcommax_ipq50xx +flock +ubi-utils
endef

define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./src/* $(PKG_BUILD_DIR)/
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_CPPFLAGS) -Wall -Wextra \
		-o $(PKG_BUILD_DIR)/ex511-v2-caldata $(PKG_BUILD_DIR)/caldata.c $(TARGET_LDFLAGS)
endef

define Package/ex511-v2-factory/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/ex511-v2-caldata $(1)/usr/bin/
endef

$(eval $(call BuildPackage,ex511-v2-factory))
