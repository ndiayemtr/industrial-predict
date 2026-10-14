import { DOCUMENT } from '@angular/common';
import { AfterRenderRef, Component, DestroyRef, ElementRef, HostListener, Injector, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationCancel, NavigationEnd, NavigationError, NavigationStart, Router, RouterOutlet } from '@angular/router';
import { NbLayoutModule, NbSidebarModule } from '@nebular/theme';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { HeaderComponent } from '../header/header.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [NbLayoutModule, NbSidebarModule, RouterOutlet, SidebarComponent, HeaderComponent],
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss'
})
export class ShellComponent {
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  private readonly destroyRef = inject(DestroyRef);
  private readonly main = viewChild.required<ElementRef<HTMLElement>>('mainContent');
  readonly currentUrl = signal(this.router.url);
  private interactionRevision = 0;
  private pendingFocus?: AfterRenderRef;
  private navigation?: { previousPath: string; focused: Element | null; revision: number };

  constructor() {
    this.destroyRef.onDestroy(() => this.pendingFocus?.destroy());
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
        // Initial load, same-page updates and fragment destinations keep their focus.
        if (!navigation || destination.fragment !== null ||
            navigation.previousPath === this.pathOf(event.urlAfterRedirects)) return;
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
    this.main().nativeElement.focus();
  }
}
