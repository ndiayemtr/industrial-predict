import { DOCUMENT } from '@angular/common';
import { AfterRenderRef, Component, DestroyRef, ElementRef, HostListener, Injector, Renderer2, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationCancel, NavigationEnd, NavigationError, NavigationStart, Router, RouterOutlet } from '@angular/router';
import { NbLayoutModule, NbSidebarComponent, NbSidebarModule, NbSidebarState } from '@nebular/theme';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { HeaderComponent } from '../header/header.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [NbLayoutModule, NbSidebarModule, RouterOutlet, SidebarComponent, HeaderComponent, CdkTrapFocus],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss'
})
export class ShellComponent {
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly destroyRef = inject(DestroyRef);
  private readonly renderer = inject(Renderer2);
  private readonly main = viewChild.required<ElementRef<HTMLElement>>('mainContent');
  private readonly sidebar = viewChild(NbSidebarComponent);
  private readonly header = viewChild.required(HeaderComponent);
  private readonly drawerClose = viewChild<ElementRef<HTMLButtonElement>>('drawerClose');
  private readonly sidebarElement = viewChild<NbSidebarComponent, ElementRef<HTMLElement>>('sidebar', { read: ElementRef });
  // The Shell owns the mode; Nebular remains the source of sidebar state.
  readonly mobile = signal((this.document.defaultView?.innerWidth ?? 1024) < 1024);
  readonly initialSidebarState: NbSidebarState = this.mobile() ? 'collapsed' : 'expanded';
  private drawerFocus?: AfterRenderRef;
  readonly currentUrl = signal(this.router.url);
  private interactionRevision = 0;
  private pendingFocus?: AfterRenderRef;
  private navigation?: { previousPath: string; focused: Element | null; revision: number };

  constructor() {
    const unlisten = this.renderer.listen('window', 'resize', () => {
      const mobile = (this.document.defaultView?.innerWidth ?? 1024) < 1024;
      if (mobile === this.mobile()) return;
      this.drawerFocus?.destroy();
      const focusedInSidebar = this.sidebarElement()?.nativeElement.contains(this.document.activeElement);
      const focusedCloseButton = this.drawerClose()?.nativeElement === this.document.activeElement;
      this.mobile.set(mobile);
      if (mobile) {
        this.sidebar()?.collapse();
        if (focusedInSidebar) this.restoreToggleFocus();
      } else {
        this.sidebar()?.expand();
        if (focusedCloseButton) this.restoreToggleFocus();
      }
    });
    this.destroyRef.onDestroy(() => {
      unlisten();
      this.pendingFocus?.destroy();
      this.drawerFocus?.destroy();
    });
    this.router.events.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((event) => {
      if (event instanceof NavigationStart) {
        this.pendingFocus?.destroy();
        this.navigation = {
          previousPath: this.pathOf(this.router.url),
          focused: this.document.activeElement,
          revision: this.interactionRevision
        };
      } else if (event instanceof NavigationCancel || event instanceof NavigationError) {
        this.navigation = undefined;
        this.pendingFocus?.destroy();
      } else if (event instanceof NavigationEnd) {
        this.currentUrl.set(event.urlAfterRedirects);
        const navigation = this.navigation;
        this.navigation = undefined;
        const destination = this.router.parseUrl(event.urlAfterRedirects);
        const drawerWasOpen = this.drawerOpen();
        if (drawerWasOpen) this.closeMobileSidebar(false);
        // Initial load, same-page updates and fragment destinations keep their focus.
        if (!navigation || destination.fragment !== null ||
            navigation.previousPath === this.pathOf(event.urlAfterRedirects)) {
          if (drawerWasOpen) this.restoreToggleFocus(true);
          return;
        }
        this.pendingFocus = afterNextRender(() => {
          this.pendingFocus = undefined;
          const focused = this.document.activeElement;
          const focusWasClaimed = focused !== navigation.focused &&
            focused !== this.document.body && focused !== this.document.documentElement;
          const focusIsOutsideShell = focused !== this.document.body &&
            focused !== this.document.documentElement && focused !== null &&
            !this.host.nativeElement.contains(focused);
          // Respect a user's interaction or a page/dialog that has claimed focus.
          if (navigation.revision !== this.interactionRevision || focusWasClaimed || focusIsOutsideShell) return;
          this.main().nativeElement.focus({ preventScroll: true });
        }, { injector: this.injector });
      }
    });
  }

  drawerOpen(): boolean {
    return this.mobile() && this.sidebar()?.state === 'expanded';
  }

  onSidebarStateChange(state: NbSidebarState): void {
    this.drawerFocus?.destroy();
    if (this.mobile() && state === 'expanded') {
      this.drawerFocus = afterNextRender(() => {
        this.drawerFocus = undefined;
        if (this.drawerOpen()) this.drawerClose()?.nativeElement.focus();
      }, { injector: this.injector });
    }
  }

  closeMobileSidebar(restoreFocus = true): void {
    if (!this.drawerOpen()) return;
    this.drawerFocus?.destroy();
    this.sidebar()?.collapse();
    if (restoreFocus) this.restoreToggleFocus();
  }

  private restoreToggleFocus(onlyIfFocusHidden = false): void {
    this.drawerFocus?.destroy();
    this.drawerFocus = afterNextRender(() => {
      this.drawerFocus = undefined;
      const focused = this.document.activeElement;
      if (!onlyIfFocusHidden || focused === this.document.body ||
          this.sidebarElement()?.nativeElement.contains(focused)) {
        this.header().focusNavigationToggle();
      }
    }, { injector: this.injector });
  }

  @HostListener('keydown.escape', ['$event'])
  closeOnEscape(event: Event): void {
    if (!this.drawerOpen()) return;
    event.preventDefault();
    event.stopPropagation();
    this.closeMobileSidebar();
  }

  private pathOf(url: string): string {
    return url.split(/[?#]/, 1)[0];
  }

  // Angular owns these scoped listeners and removes them with the Shell.
  @HostListener('pointerdown')
  @HostListener('keydown')
  @HostListener('focusin')
  protectInteraction(): void {
    this.interactionRevision += 1;
    this.pendingFocus?.destroy();
    this.pendingFocus = undefined;
  }

  skipToContent(event: Event): void {
    event.preventDefault();
    this.closeMobileSidebar(false);
    this.main().nativeElement.focus();
  }
}
