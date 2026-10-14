import { ChangeDetectionStrategy, Component, ElementRef, computed, inject, input, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, PRIMARY_OUTLET, Router } from '@angular/router';
import { NbSidebarService, NbSidebarState } from '@nebular/theme';
import { filter, map, startWith } from 'rxjs';
import { IconComponent } from '../../shared/ui/icon/icon.component';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './header.component.html',
  styleUrl: './header.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class HeaderComponent {
  private readonly toggleButton = viewChild.required<ElementRef<HTMLButtonElement>>('toggleButton');
  readonly sidebarState = input.required<NbSidebarState>();
  readonly sidebarTag = input.required<string>();
  readonly sidebarId = input.required<string>();
  readonly expanded = computed(() => this.sidebarState() === 'expanded');
  private readonly router = inject(Router);
  private readonly sidebar = inject(NbSidebarService);

  readonly title = toSignal(this.router.events.pipe(
    filter((event) => event instanceof NavigationEnd),
    startWith(null),
    map(() => {
      let route = this.router.routerState.snapshot.root;
      let title = 'Espace de travail';
      while (route) {
        const pageTitle = route.data['pageTitle'];
        if (typeof pageTitle === 'string' && pageTitle.trim()) title = pageTitle.trim();
        const child = route.children.find((candidate) => candidate.outlet === PRIMARY_OUTLET);
        if (!child) break;
        route = child;
      }
      return title;
    })
  ), { requireSync: true });

  toggleSidebar(): void {
    // Nebular 17: false toggles expanded/collapsed; true would use compacted.
    // The actual NbSidebarComponent state remains the single source of truth.
    this.sidebar.toggle(false, this.sidebarTag());
  }

  focusNavigationToggle(): void {
    this.toggleButton().nativeElement.focus({ preventScroll: true });
  }
}
