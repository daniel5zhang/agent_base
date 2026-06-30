"use client";

import type * as React from "react";
import { BadgeCheckIcon, SettingsIcon } from "lucide-react";

import { ThreadList } from "@/components/assistant-ui/thread-list";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";

function SidebarBrandButton() {
  const { isMobile, setOpen, setOpenMobile, state } = useSidebar();

  return (
    <SidebarMenuButton
      size="lg"
      isActive
      tooltip="企业 Agent 工作台"
      aria-label={state === "collapsed" ? "展开左侧会话列表" : "企业 Agent 工作台"}
      onClick={() => {
        if (isMobile) {
          setOpenMobile(true);
          return;
        }
        if (state === "collapsed") {
          setOpen(true);
        }
      }}
    >
      <div className="aui-sidebar-header-icon-wrapper bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
        <BadgeCheckIcon className="aui-sidebar-header-icon size-4" />
      </div>
      <div className="aui-sidebar-header-heading me-6 flex flex-col gap-0.5 leading-none">
        <span className="aui-sidebar-header-title font-semibold group-data-[collapsible=icon]:hidden">
          企业 Agent 工作台
        </span>
      </div>
    </SidebarMenuButton>
  );
}

export function ThreadListSidebar({
  onOpenSettings,
  ...props
}: React.ComponentProps<typeof Sidebar> & {
  onOpenSettings?: () => void;
}) {
  return (
    <Sidebar {...props}>
      <SidebarHeader className="aui-sidebar-header mb-2 border-b">
        <div className="aui-sidebar-header-content flex items-center justify-between">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarBrandButton />
            </SidebarMenuItem>
          </SidebarMenu>
          <SidebarTrigger
            className="aui-sidebar-trigger size-8 shrink-0"
            aria-label="折叠左侧会话列表"
          />
        </div>
      </SidebarHeader>
      <SidebarContent className="aui-sidebar-content px-2">
        <ThreadList />
      </SidebarContent>
      <SidebarRail />
      <SidebarFooter className="aui-sidebar-footer border-t">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" tooltip="设置与模型" onClick={onOpenSettings}>
              <div className="aui-sidebar-footer-icon-wrapper bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                <SettingsIcon className="aui-sidebar-footer-icon size-4" />
              </div>
              <div className="aui-sidebar-footer-heading flex flex-col gap-0.5 leading-none group-data-[collapsible=icon]:hidden">
                <span className="aui-sidebar-footer-title font-semibold">
                  设置与模型
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
